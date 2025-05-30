#!/usr/bin/env python3

import requests
import time
import os

BASE_URL = "http://172.31.3.236:8000"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_root():
    """Test root endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"Root endpoint: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Root endpoint failed: {e}")
        return False

def create_dummy_pdf():
    """Create a minimal dummy PDF for testing"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        filename = "test_dummy.pdf"
        c = canvas.Canvas(filename, pagesize=letter)
        c.drawString(100, 750, "Test PDF for API Testing")
        c.drawString(100, 700, "P-101A")  # Sample tag
        c.drawString(100, 650, "BV-0007")  # Sample tag
        c.save()
        
        return filename
    except ImportError:
        print("reportlab not installed, creating minimal PDF file")
        # Create a minimal PDF manually
        filename = "test_minimal.pdf"
        with open(filename, 'wb') as f:
            # Minimal PDF content
            pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000010 00000 n 
0000000053 00000 n 
0000000125 00000 n 
0000000185 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
279
%%EOF"""
            f.write(pdf_content)
        
        return filename

def test_pdf_validation():
    """Test PDF validation endpoint"""
    try:
        pdf_file = create_dummy_pdf()
        
        with open(pdf_file, 'rb') as f:
            files = {'file': (pdf_file, f, 'application/pdf')}
            response = requests.post(
                f"{BASE_URL}/validate-pdf",
                files=files,
                timeout=30
            )
        
        print(f"PDF validation: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
        
        # Clean up
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
            
        return response.status_code == 200
        
    except Exception as e:
        print(f"PDF validation test failed: {e}")
        return False

def test_extract_tags_sync():
    """Test synchronous tag extraction"""
    try:
        pdf_file = create_dummy_pdf()
        
        with open(pdf_file, 'rb') as f:
            files = {'file': (pdf_file, f, 'application/pdf')}
            data = {
                'gemini_model': 'gemini-1.5-flash-latest',
                'pdf_conversion_dpi': 200
            }
            response = requests.post(
                f"{BASE_URL}/test-single-pdf",
                files=files,
                data=data,
                timeout=120  # Longer timeout for processing
            )
        
        print(f"Sync tag extraction: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Tags found: {result.get('total_unique_tags', 0)}")
            print(f"Processing time: {result.get('processing_time', 0):.2f}s")
        else:
            print(f"Error: {response.text}")
        
        # Clean up
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
            
        return response.status_code == 200
        
    except Exception as e:
        print(f"Sync tag extraction test failed: {e}")
        return False

def test_extract_tags_async():
    """Test asynchronous tag extraction"""
    try:
        pdf_file = create_dummy_pdf()
        
        # Start async processing
        with open(pdf_file, 'rb') as f:
            files = {'files': (pdf_file, f, 'application/pdf')}
            data = {
                'gemini_model': 'gemini-1.5-flash-latest',
                'pdf_conversion_dpi': 200
            }
            response = requests.post(
                f"{BASE_URL}/extract-tags",
                files=files,
                data=data,
                timeout=30
            )
        
        print(f"Async tag extraction start: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"Task ID: {task_id}")
            
            # Poll for status
            max_attempts = 30  # 5 minutes max
            for attempt in range(max_attempts):
                status_response = requests.get(f"{BASE_URL}/status/{task_id}", timeout=10)
                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"Status: {status.get('status')} - {status.get('progress', '')}")
                    
                    if status.get('status') == 'completed':
                        # Get final result
                        result_response = requests.get(f"{BASE_URL}/result/{task_id}", timeout=10)
                        if result_response.status_code == 200:
                            final_result = result_response.json()
                            print(f"Final result - Tags: {final_result.get('total_unique_tags', 0)}")
                            return True
                        else:
                            print(f"Failed to get result: {result_response.text}")
                            return False
                    elif status.get('status') == 'failed':
                        print(f"Processing failed: {status.get('error')}")
                        return False
                
                time.sleep(10)  # Wait 10 seconds before next check
            
            print("Timeout waiting for completion")
            return False
        else:
            print(f"Error starting async processing: {response.text}")
            return False
        
    except Exception as e:
        print(f"Async tag extraction test failed: {e}")
        return False
    finally:
        # Clean up
        if 'pdf_file' in locals() and os.path.exists(pdf_file):
            os.remove(pdf_file)

def main():
    """Run all tests"""
    print("🧪 Starting API Tests")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health),
        ("Root Endpoint", test_root),
        ("PDF Validation", test_pdf_validation),
        ("Sync Tag Extraction", test_extract_tags_sync),
        ("Async Tag Extraction", test_extract_tags_async),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔧 Running: {test_name}")
        print("-" * 30)
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results[test_name] = False
        
        if results[test_name]:
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())
