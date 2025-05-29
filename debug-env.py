#!/usr/bin/env python3
"""
Environment Variable Debugging Script
This script helps debug issues with loading the GEMINI_API_KEY
"""

import os
import sys
from pathlib import Path

def debug_environment():
    print("🔍 GEMINI API KEY DEBUGGING")
    print("=" * 50)
    
    # 1. Check current working directory
    print(f"📁 Current working directory: {os.getcwd()}")
    
    # 2. Check if .env file exists
    env_files = ['.env', '.env.local', '.env.production', '.env.development']
    
    print(f"\n📄 Environment files check:")
    for env_file in env_files:
        exists = os.path.exists(env_file)
        print(f"   {env_file}: {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
        
        if exists:
            try:
                with open(env_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        print(f"      Content preview:")
                        lines = content.split('\n')
                        for i, line in enumerate(lines[:5], 1):  # Show first 5 lines
                            if '=' in line and 'GEMINI' in line.upper():
                                key, value = line.split('=', 1)
                                print(f"      {i}: {key}={'*' * min(10, len(value))}")
                            elif line.strip():
                                print(f"      {i}: {line}")
                        if len(lines) > 5:
                            print(f"      ... and {len(lines) - 5} more lines")
                    else:
                        print(f"      ⚠️  File is empty")
            except Exception as e:
                print(f"      ❌ Error reading file: {e}")
    
    # 3. Check environment variables before loading .env
    print(f"\n🌍 Environment variables (before loading .env):")
    gemini_vars_before = {k: v for k, v in os.environ.items() if 'GEMINI' in k.upper()}
    if gemini_vars_before:
        for key, value in gemini_vars_before.items():
            print(f"   {key}: {'*' * min(10, len(value))}")
    else:
        print("   No GEMINI-related variables found")
    
    # 4. Try loading .env file manually
    print(f"\n🔧 Attempting to load .env files:")
    
    try:
        from dotenv import load_dotenv
        print("   ✅ python-dotenv imported successfully")
        
        # Try loading different .env files
        for env_file in env_files:
            if os.path.exists(env_file):
                result = load_dotenv(env_file, verbose=True)
                print(f"   load_dotenv('{env_file}'): {'✅ SUCCESS' if result else '❌ FAILED'}")
        
        # Try default load_dotenv()
        result = load_dotenv(verbose=True)
        print(f"   load_dotenv(): {'✅ SUCCESS' if result else '❌ FAILED'}")
        
    except ImportError:
        print("   ❌ python-dotenv not installed")
        print("   Run: pip install python-dotenv")
    except Exception as e:
        print(f"   ❌ Error loading .env: {e}")
    
    # 5. Check environment variables after loading .env
    print(f"\n🌍 Environment variables (after loading .env):")
    gemini_vars_after = {k: v for k, v in os.environ.items() if 'GEMINI' in k.upper()}
    if gemini_vars_after:
        for key, value in gemini_vars_after.items():
            print(f"   {key}: {'*' * min(10, len(value))} (length: {len(value)})")
    else:
        print("   No GEMINI-related variables found")
    
    # 6. Test API key access
    print(f"\n🔑 Testing API key access:")
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        print(f"   ✅ GEMINI_API_KEY found")
        print(f"   Length: {len(api_key)} characters")
        print(f"   Starts with: {api_key[:10]}...")
        print(f"   Ends with: ...{api_key[-10:]}")
        
        # Test if it looks like a valid API key
        if api_key.startswith('AIza') and len(api_key) == 39:
            print(f"   ✅ Format looks like a valid Google API key")
        else:
            print(f"   ⚠️  Format doesn't match expected Google API key pattern")
            print(f"   Expected: Starts with 'AIza' and 39 characters long")
    else:
        print(f"   ❌ GEMINI_API_KEY not found")
    
    # 7. Test Gemini API configuration
    print(f"\n🤖 Testing Gemini API configuration:")
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            print(f"   ✅ Gemini API configured successfully")
            
            # Try to list models as a test
            try:
                models = list(genai.list_models())
                print(f"   ✅ API connection test successful ({len(models)} models available)")
            except Exception as e:
                print(f"   ⚠️  API key configured but connection test failed: {e}")
                
        except ImportError:
            print(f"   ❌ google-generativeai not installed")
            print(f"   Run: pip install google-generativeai")
        except Exception as e:
            print(f"   ❌ Error configuring Gemini API: {e}")
    else:
        print(f"   ⏭️  Skipped (no API key found)")
    
    # 8. Provide recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    if not os.path.exists('.env'):
        print("   1. Create a .env file in your project root directory")
    
    if not api_key:
        print("   2. Add your API key to .env file:")
        print("      GEMINI_API_KEY=your_actual_api_key_here")
        print("   3. Make sure there are no spaces around the = sign")
        print("   4. Make sure the .env file is in the same directory as main.py")
    
    if api_key and not api_key.startswith('AIza'):
        print("   2. Check if your API key is correct")
        print("   3. Get a new API key from: https://makersuite.google.com/app/apikey")
    
    print("   4. Make sure python-dotenv is installed: pip install python-dotenv")
    print("   5. Restart your FastAPI server after making changes")
    
    print(f"\n🚀 Ready to test? Run your FastAPI server and check the startup logs!")

if __name__ == "__main__":
    debug_environment()