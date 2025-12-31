import requests
import sys
import base64
import io
from PIL import Image
import json
from datetime import datetime

class PhotoAnalysisAPITester:
    def __init__(self, base_url="https://pic-filter-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.uploaded_photo_ids = []

    def create_test_image(self, width=200, height=200, color=(255, 0, 0)):
        """Create a test image with some visual features"""
        img = Image.new('RGB', (width, height), color)
        # Add some visual features - a simple pattern
        for x in range(0, width, 20):
            for y in range(0, height, 20):
                if (x + y) % 40 == 0:
                    img.putpixel((x, y), (0, 255, 0))
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        return buffer.getvalue()

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers)
                else:
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test("Root Endpoint", "GET", "", 200)

    def test_analyze_photos(self):
        """Test photo analysis endpoint with multiple images"""
        # Create test images
        test_images = []
        for i in range(2):
            img_data = self.create_test_image(
                color=(255 if i == 0 else 0, 128, 255 if i == 1 else 0)
            )
            test_images.append(('files', (f'test_image_{i}.jpg', img_data, 'image/jpeg')))
        
        success, response = self.run_test(
            "Analyze Photos",
            "POST",
            "analyze",
            200,
            files=test_images
        )
        
        if success and 'photos' in response:
            self.uploaded_photo_ids = [photo['id'] for photo in response['photos']]
            print(f"   Uploaded {len(self.uploaded_photo_ids)} photos")
            
            # Verify response structure
            for photo in response['photos']:
                required_fields = ['id', 'filename', 'sharpness_score', 'noise_score', 
                                 'composition_score', 'exposure_score', 'overall_score', 
                                 'is_good', 'analysis_text']
                for field in required_fields:
                    if field not in photo:
                        print(f"❌ Missing field '{field}' in photo response")
                        return False
                    
                # Verify score ranges
                score_fields = ['sharpness_score', 'noise_score', 'composition_score', 'exposure_score', 'overall_score']
                for field in score_fields:
                    score = photo[field]
                    if not (0 <= score <= 10):
                        print(f"❌ Score '{field}' out of range: {score}")
                        return False
            
            print("✅ Photo analysis response structure is valid")
            return True
        
        return success

    def test_get_all_photos(self):
        """Test getting all photos"""
        success, response = self.run_test("Get All Photos", "GET", "photos", 200)
        
        if success and isinstance(response, list):
            print(f"   Retrieved {len(response)} photos")
            return True
        return success

    def test_get_filtered_photos(self):
        """Test getting filtered photos"""
        # Test good photos filter
        success_good, response_good = self.run_test(
            "Get Good Photos", "GET", "photos", 200, data={"filter": "good"}
        )
        
        # Test bad photos filter
        success_bad, response_bad = self.run_test(
            "Get Bad Photos", "GET", "photos", 200, data={"filter": "bad"}
        )
        
        if success_good and success_bad:
            good_count = len(response_good) if isinstance(response_good, list) else 0
            bad_count = len(response_bad) if isinstance(response_bad, list) else 0
            print(f"   Good photos: {good_count}, Bad photos: {bad_count}")
            return True
        
        return success_good and success_bad

    def test_delete_photo(self):
        """Test deleting a specific photo"""
        if not self.uploaded_photo_ids:
            print("⚠️  No photos to delete, skipping test")
            return True
        
        photo_id = self.uploaded_photo_ids[0]
        success, _ = self.run_test(
            f"Delete Photo {photo_id}", "DELETE", f"photos/{photo_id}", 200
        )
        
        if success:
            self.uploaded_photo_ids.remove(photo_id)
        
        return success

    def test_delete_nonexistent_photo(self):
        """Test deleting a non-existent photo"""
        fake_id = "nonexistent-photo-id"
        success, _ = self.run_test(
            "Delete Non-existent Photo", "DELETE", f"photos/{fake_id}", 404
        )
        return success

    def test_delete_all_photos(self):
        """Test deleting all photos"""
        return self.run_test("Delete All Photos", "DELETE", "photos", 200)

def main():
    print("🚀 Starting Photo Analysis API Tests")
    print("=" * 50)
    
    tester = PhotoAnalysisAPITester()
    
    # Test sequence
    tests = [
        ("Root Endpoint", tester.test_root_endpoint),
        ("Photo Analysis", tester.test_analyze_photos),
        ("Get All Photos", tester.test_get_all_photos),
        ("Get Filtered Photos", tester.test_get_filtered_photos),
        ("Delete Specific Photo", tester.test_delete_photo),
        ("Delete Non-existent Photo", tester.test_delete_nonexistent_photo),
        ("Delete All Photos", tester.test_delete_all_photos),
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            test_func()
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {str(e)}")
    
    # Print final results
    print(f"\n{'='*50}")
    print(f"📊 FINAL RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "No tests run")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())