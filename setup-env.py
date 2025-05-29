#!/usr/bin/env python3
"""
Environment Setup Script
This script helps you set up the .env file with your Gemini API key
"""

import os
import sys
from pathlib import Path

def setup_environment():
    print("🚀 PDF Tag Extraction Service - Environment Setup")
    print("=" * 55)
    
    # Check if .env already exists
    if os.path.exists('.env'):
        print("📄 Found existing .env file")
        
        # Read existing content
        try:
            with open('.env', 'r') as f:
                content = f.read()
                if 'GEMINI_API_KEY' in content:
                    print("✅ GEMINI_API_KEY already exists in .env file")
                    
                    # Ask if user wants to update it
                    update = input("\n🤔 Do you want to update the API key? (y/N): ").lower().strip()
                    if update not in ['y', 'yes']:
                        print("✅ Keeping existing configuration")
                        return verify_setup()
                else:
                    print("⚠️  GEMINI_API_KEY not found in existing .env file")
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
    
    # Get API key from user
    print("\n🔑 Gemini API Key Setup")
    print("If you don't have an API key, get one from:")
    print("👉 https://makersuite.google.com/app/apikey")
    print()
    
    api_key = input("Please enter your Gemini API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Setup cancelled.")
        return False
    
    # Basic validation
    if not api_key.startswith('AIza'):
        print("⚠️  Warning: API key doesn't start with 'AIza'")
        print("   Make sure you copied the complete key")
        confirm = input("   Continue anyway? (y/N): ").lower().strip()
        if confirm not in ['y', 'yes']:
            print("Setup cancelled.")
            return False
    
    if len(api_key) != 39:
        print(f"⚠️  Warning: API key length is {len(api_key)}, expected 39 characters")
        print("   Make sure you copied the complete key")
        confirm = input("   Continue anyway? (y/N): ").lower().strip()
        if confirm not in ['y', 'yes']:
            print("Setup cancelled.")
            return False
    
    # Create or update .env file
    try:
        env_content = f"# Gemini API Configuration\nGEMINI_API_KEY={api_key}\n"
        
        # If .env exists, preserve other variables
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                existing_content = f.read()
            
            # Remove existing GEMINI_API_KEY lines
            lines = existing_content.split('\n')
            filtered_lines = [line for line in lines if not line.strip().startswith('GEMINI_API_KEY')]
            
            # Add new API key
            if filtered_lines and filtered_lines[-1].strip():
                filtered_lines.append('')  # Add blank line
            filtered_lines.append('# Gemini API Configuration')
            filtered_lines.append(f'GEMINI_API_KEY={api_key}')
            
            env_content = '\n'.join(filtered_lines)
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("✅ .env file created/updated successfully!")
        
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False
    
    return verify_setup()

def verify_setup():
    """Verify that the setup is working correctly"""
    print("\n🔍 Verifying setup...")
    
    try:
        # Import and load dotenv
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check if API key is accessible
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            print("✅ API key loaded successfully")
            print(f"   Length: {len(api_key)} characters")
            print(f"   Preview: {api_key[:10]}...{api_key[-5:]}")
            
            # Test Gemini API
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Try a simple API call
                models = list(genai.list_models())
                print(f"✅ Gemini API connection successful!")
                print(f"   Available models: {len(models)}")
                
                return True
                
            except ImportError:
                print("⚠️  google-generativeai not installed")
                print("   Run: pip install google-generativeai")
                return False
            except Exception as e:
                print(f"❌ Gemini API connection failed: {e}")
                print("   Please check your API key")
                return False
        else:
            print("❌ API key not found after setup")
            return False
            
    except ImportError:
        print("❌ python-dotenv not installed")
        print("   Run: pip install python-dotenv")
        return False
    except Exception as e:
        print(f"❌ Setup verification failed: {e}")
        return False

def main():
    success = setup_environment()
    
    if success:
        print("\n🎉 Setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Start the server: python main.py")
        print("   or: uvicorn main:app --reload")
        print("3. Test the API: http://localhost:8000/health")
    else:
        print("\n❌ Setup failed. Please try again or debug manually.")
        print("\nFor debugging, run: python debug_env.py")

if __name__ == "__main__":
    main()