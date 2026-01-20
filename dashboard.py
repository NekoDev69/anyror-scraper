#!/usr/bin/env python3
"""
Web Dashboard for Gujarat AnyROR Scraper with Swarm Search
Select district and start concurrent scraping with configurable workers
"""

from flask import Flask, render_template, request, jsonify
import json
import os
import threading
from datetime import datetime
from swarm_scraper import SwarmScraper

app = Flask(__name__)

# Global state
scraper_instance = None
scraper_thread = None
scraper_state = {
    "running": False,
    "progress": {
        "status": "idle",
        "district_name": "",
        "current_taluka": "",
        "villages_total": 0,
        "villages_completed": 0,
        "villages_successful": 0,
        "villages_failed": 0,
        "active_workers": 0,
        "villages_per_minute": 0,
        "eta_seconds": 0,
        "start_time": None
    },
    "results": []
}

# Load zone data
zone_file = 'data/gujarat-anyror-complete.json'
if not os.path.exists(zone_file):
    if os.path.exists('frontend/gujarat-anyror-complete.json'):
        zone_file = 'frontend/gujarat-anyror-complete.json'
    else:
        zone_file = 'gujarat-anyror-complete.json'

if os.path.exists(zone_file):
    with open(zone_file, 'r', encoding='utf-8') as f:
        ZONE_DATA = json.load(f)
else:
    print(f"[ERROR] Zone data file not found!")
    ZONE_DATA = {'districts': []}


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/districts')
def get_districts():
    """Get list of all districts"""
    districts = []
    for d in ZONE_DATA['districts']:
        districts.append({
            'code': d['value'],
            'name': d['label'],
            'talukas_count': len(d['talukas']),
            'villages_count': sum(len(t['villages']) for t in d['talukas'])
        })
    return jsonify(districts)


@app.route('/api/district/<district_code>')
def get_district_info(district_code):
    """Get detailed info for a specific district"""
    district = next((d for d in ZONE_DATA['districts'] if d['value'] == district_code), None)
    if not district:
        return jsonify({'error': 'District not found'}), 404
    
    talukas = []
    for t in district['talukas']:
        talukas.append({
            'code': t['value'],
            'name': t['label'],
            'villages_count': len(t['villages'])
        })
    
    return jsonify({
        'code': district['value'],
        'name': district['label'],
        'talukas': talukas,
        'total_villages': sum(len(t['villages']) for t in district['talukas'])
    })


@app.route('/api/start', methods=['POST'])
def start_scraping():
    """Start swarm scraping a district"""
    global scraper_instance, scraper_thread, scraper_state
    
    if scraper_state['running']:
        return jsonify({'error': 'Scraper already running'}), 400
    
    data = request.json
    district_code = data.get('district_code')
    num_workers = data.get('num_workers', 10)
    max_villages_per_taluka = data.get('max_villages_per_taluka')
    
    if not district_code:
        return jsonify({'error': 'District code required'}), 400
    
    # Validate workers
    num_workers = min(max(1, int(num_workers)), 20)  # Clamp 1-20
    
    # Find district
    district = next((d for d in ZONE_DATA['districts'] if d['value'] == district_code), None)
    if not district:
        return jsonify({'error': 'District not found'}), 404
    
    # Prepare talukas with optional village limit
    talukas = []
    for t in district['talukas']:
        villages = t['villages']
        if max_villages_per_taluka:
            villages = villages[:int(max_villages_per_taluka)]
        talukas.append({
            'value': t['value'],
            'label': t['label'],
            'villages': villages
        })
    
    total_villages = sum(len(t['villages']) for t in talukas)
    
    # Reset state
    scraper_state['running'] = True
    scraper_state['progress'] = {
        'status': 'starting',
        'district_name': district['label'],
        'current_taluka': '',
        'villages_total': total_villages,
        'villages_completed': 0,
        'villages_successful': 0,
        'villages_failed': 0,
        'active_workers': 0,
        'villages_per_minute': 0,
        'eta_seconds': 0,
        'start_time': datetime.now().isoformat()
    }
    scraper_state['results'] = []
    
    # Create scraper
    scraper_instance = SwarmScraper(num_workers=num_workers, headless=True)
    
    # Start scraping in background thread
    scraper_thread = threading.Thread(
        target=run_swarm_scraper,
        args=(district_code, district['label'], talukas)
    )
    scraper_thread.daemon = True
    scraper_thread.start()
    
    return jsonify({
        'status': 'started',
        'district': district['label'],
        'total_villages': total_villages,
        'num_workers': num_workers
    })


def run_swarm_scraper(district_code, district_name, talukas):
    """Run swarm scraper in background"""
    global scraper_instance, scraper_state
    
    try:
        # Run the swarm scraper
        result = scraper_instance.scrape_district(
            district_code=district_code,
            district_name=district_name,
            talukas=talukas,
            output_dir='output'
        )
        
        scraper_state['results'] = result.get('results', [])
        scraper_state['progress']['status'] = 'completed'
        scraper_state['progress']['villages_successful'] = result['successful']
        scraper_state['progress']['villages_failed'] = result['failed']
        
    except Exception as e:
        print(f"Swarm scraper error: {e}")
        import traceback
        traceback.print_exc()
        scraper_state['progress']['status'] = 'error'
        scraper_state['progress']['error'] = str(e)
    finally:
        scraper_state['running'] = False
        scraper_state['progress']['end_time'] = datetime.now().isoformat()


@app.route('/api/status')
def get_status():
    """Get current scraping status with live updates"""
    global scraper_instance, scraper_state
    
    # Get live progress from scraper if running
    if scraper_instance and scraper_state['running']:
        live_progress = scraper_instance.get_progress()
        scraper_state['progress'].update({
            'status': live_progress.get('status', 'running'),
            'current_taluka': live_progress.get('current_taluka', ''),
            'villages_completed': live_progress.get('villages_completed', 0),
            'villages_successful': live_progress.get('villages_successful', 0),
            'villages_failed': live_progress.get('villages_failed', 0),
            'active_workers': live_progress.get('active_workers', 0),
            'villages_per_minute': live_progress.get('villages_per_minute', 0),
            'eta_seconds': live_progress.get('eta_seconds', 0),
        })
    
    return jsonify({
        'running': scraper_state['running'],
        'progress': scraper_state['progress']
    })


@app.route('/api/stop', methods=['POST'])
def stop_scraping():
    """Stop the scraper"""
    global scraper_instance, scraper_state
    
    if scraper_instance:
        scraper_instance.stop()
    
    scraper_state['running'] = False
    scraper_state['progress']['status'] = 'stopped'
    
    return jsonify({'status': 'stopped'})


@app.route('/api/results')
def get_results():
    """Get scraping results"""
    results = scraper_state.get('results', [])
    
    return jsonify({
        'results': results,
        'summary': {
            'total': len(results),
            'successful': sum(1 for r in results if r.get('success')),
            'failed': sum(1 for r in results if not r.get('success'))
        }
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🐝 Gujarat AnyROR Swarm Scraper Dashboard")
    print("=" * 60)
    print("\nStarting server...")
    print("Open your browser to: http://localhost:5001")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
