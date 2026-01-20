#!/usr/bin/env python3
"""
Check Vertex AI Quota Limits
Simple script to view your current Vertex AI rate limits
"""

import subprocess
import json
import sys

PROJECT_ID = "anyror-scraper-2026"

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        return result.stdout, result.returncode
    except Exception as e:
        return f"Error: {e}", 1

def check_limits():
    """Check Vertex AI limits using multiple methods"""
    
    print("🔍 Checking Vertex AI Quotas")
    print("=" * 60)
    print(f"Project: {PROJECT_ID}")
    print()
    
    # Method 1: Try gcloud alpha
    print("📊 Method 1: Using gcloud CLI")
    print("-" * 60)
    
    cmd = f"""gcloud alpha services quota list \
        --service=aiplatform.googleapis.com \
        --project={PROJECT_ID} \
        --filter="metric.name:generate_content_requests_per_minute" \
        --format=json 2>/dev/null"""
    
    output, code = run_command(cmd)
    
    if code == 0 and output.strip():
        try:
            quotas = json.loads(output)
            if quotas:
                print("✅ Found quotas:")
                for quota in quotas:
                    metric = quota.get('metric', {})
                    print(f"\n  Quota: {metric.get('displayName', 'N/A')}")
                    print(f"  Limit: {quota.get('limit', 'N/A')}")
                    print(f"  Usage: {quota.get('usage', 'N/A')}")
                    if 'dimensions' in quota:
                        print(f"  Dimensions: {quota['dimensions']}")
            else:
                print("⚠️  No quotas found in response")
        except json.JSONDecodeError:
            print("⚠️  Unable to parse gcloud output")
    else:
        print("⚠️  gcloud alpha not available or command failed")
        print("   Install: gcloud components install alpha")
    
    print()
    print("-" * 60)
    print()
    
    # Method 2: Check via API
    print("📊 Method 2: Using Service Usage API")
    print("-" * 60)
    
    # Get access token
    token_cmd = "gcloud auth print-access-token 2>/dev/null"
    token, code = run_command(token_cmd)
    
    if code == 0 and token.strip():
        token = token.strip()
        
        # Query API
        api_cmd = f"""curl -s -H "Authorization: Bearer {token}" \
            "https://serviceusage.googleapis.com/v1/projects/{PROJECT_ID}/services/aiplatform.googleapis.com/consumerQuotaMetrics" """
        
        output, code = run_command(api_cmd)
        
        if code == 0 and output.strip():
            try:
                data = json.loads(output)
                found = False
                
                if 'metrics' in data:
                    for metric in data['metrics']:
                        if 'generate_content_requests_per_minute' in metric.get('metric', ''):
                            found = True
                            print(f"✅ {metric.get('displayName', 'N/A')}")
                            print(f"   Metric: {metric.get('metric', 'N/A')}")
                            
                            if 'consumerQuotaLimits' in metric:
                                for limit in metric['consumerQuotaLimits']:
                                    if 'quotaBuckets' in limit:
                                        for bucket in limit['quotaBuckets']:
                                            effective = bucket.get('effectiveLimit', 'N/A')
                                            default = bucket.get('defaultLimit', 'N/A')
                                            print(f"\n   Current Limit: {effective} requests/minute")
                                            print(f"   Default Limit: {default} requests/minute")
                                            
                                            if 'dimensions' in bucket:
                                                dims = bucket['dimensions']
                                                if 'base_model' in dims:
                                                    print(f"   Model: {dims['base_model']}")
                
                if not found:
                    print("⚠️  No matching quotas found in API response")
                    
            except json.JSONDecodeError:
                print("⚠️  Unable to parse API response")
        else:
            print("⚠️  API request failed")
    else:
        print("⚠️  Unable to get access token")
        print("   Run: gcloud auth login")
    
    print()
    print("-" * 60)
    print()
    
    # Method 3: Console link
    print("📊 Method 3: View in Google Cloud Console")
    print("-" * 60)
    print()
    print("🌐 Open this link to see all quotas:")
    print(f"   https://console.cloud.google.com/iam-admin/quotas?project={PROJECT_ID}")
    print()
    print("Then filter by:")
    print("   • Service: Vertex AI API")
    print("   • Metric: generate_content_requests_per_minute")
    print()
    
    print("=" * 60)
    print("📋 Summary")
    print("=" * 60)
    print()
    print("Typical Vertex AI limits:")
    print("   • Development/Free: 5-60 requests/minute")
    print("   • Production: 100-1000 requests/minute")
    print("   • After quota increase: 500+ requests/minute")
    print()
    print("If you see ResourceExhausted errors, you're hitting the limit.")
    print("Request an increase using: QUICK_START_QUOTA.md")
    print()

if __name__ == "__main__":
    try:
        check_limits()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
