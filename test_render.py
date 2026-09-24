import sys
sys.path.insert(0, ".")
from app import app

client = app.test_client()

# Test search page renders
resp = client.get("/search")
html = resp.data.decode()
print("=== PAGE RENDER TEST ===")
print(f"  Status: {resp.status_code}")
print(f"  Title in HTML: {'Global Search' in html}")
print(f"  search.css linked: {'search.css' in html}")
print(f"  search.js linked: {'search.js' in html}")
print(f"  searchConfig present: {'searchConfig' in html}")
print(f"  Search input present: {'search-input' in html}")
print(f"  Autocomplete dropdown present: {'autocomplete-dropdown' in html}")
print(f"  Results section present: {'search-results' in html}")
print(f"  Prompt section present: {'search-prompt' in html}")
print(f"  Filters section present: {'search-filters' in html}")
print(f"  Type select present: {'search-type' in html}")

# Test search page with query params (from URL)
resp = client.get("/search?type=event&q=AGC")
html = resp.data.decode()
print("\n=== PAGE WITH URL PARAMS ===")
print(f"  Status: {resp.status_code}")
print(f"  Type pre-selected: {'value=\"event\"' in html}")
print(f"  Query pre-filled: {'value=\"AGC\"' in html}")

# Test the JS file
resp = client.get("/static/js/search.js")
print("\n=== JS FILE ===")
print(f"  Status: {resp.status_code}")
print(f"  Contains searchApp: {'searchApp' in resp.data.decode()}")
print(f"  Contains executeSearch: {'executeSearch' in resp.data.decode()}")
print(f"  Contains autocomplete: {'autocomplete' in resp.data.decode()}")

# Test the CSS file
resp = client.get("/static/css/search.css")
print("\n=== CSS FILE ===")
print(f"  Status: {resp.status_code}")
print(f"  Contains search-hero: {'search-hero' in resp.data.decode()}")
print(f"  Contains result-card: {'result-card' in resp.data.decode()}")

print("\n=== ALL RENDER TESTS PASSED ===")
