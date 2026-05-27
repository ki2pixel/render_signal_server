from app_render import app
from bs4 import BeautifulSoup
import sys

with app.test_client() as client:
    # Need to simulate a login or mock the login_required
    # Let's just bypass login_required or render template manually
    with app.test_request_context('/'):
        from flask import render_template
        # mock current_user if needed, but dashboard.html doesn't strictly require it
        try:
            html = render_template('dashboard.html')
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the bundled CSS
            css_links = soup.find_all('link', rel='stylesheet')
            print("CSS Links:")
            for link in css_links:
                print(link.get('href'))
                
            # Find the bundled JS
            scripts = soup.find_all('script', type='module')
            print("\nJS Scripts:")
            for script in scripts:
                print(script.get('src'))
                
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
