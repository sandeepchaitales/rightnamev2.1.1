from duckduckgo_search import DDGS
from app_store_scraper import AppStore
from google_play_scraper import app, Sort, search as google_search
import time
import random

def get_web_search_results(query, num_results=10):
    """
    Scrapes Web Search Results using DuckDuckGo.
    Returns list of titles/snippets.
    """
    results = []
    try:
        with DDGS() as ddgs:
            # use 'text' method for search
            ddg_gen = ddgs.text(query, max_results=num_results)
            for r in ddg_gen:
                results.append(f"{r['title']} ({r['href']}): {r['body']}")
            
    except Exception as e:
        results.append(f"Web Search Error: {str(e)}")
            
    return results

def get_app_store_results(query):
    """
    Searches Apple App Store (US).
    Returns list of app names.
    """
    results = []
    try:
        # Check US store
        us_store = AppStore(country='us', app_name=query)
        us_store.search(query)
        
        # app_store_scraper puts results in us_store.search_results
        if us_store.search_results:
            for app in us_store.search_results[:5]:
                results.append(f"{app['trackName']} (Developer: {app['artistName']})")
        else:
            # Fallback if empty (sometimes it prints 'no results' to stdout but list is empty)
            pass
            
    except Exception as e:
        # Don't fail the whole report if app store fails
        results.append(f"App Store Check Failed: {str(e)}")
        
    return results

def get_play_store_results(query):
    """
    Searches Google Play Store.
    """
    results = []
    try:
        res = google_search(
            query,
            lang='en',
            country='us',
            n_hits=5
        )
        
        for app in res:
            results.append(f"{app['title']} (Developer: {app['developer']})")
            
    except Exception as e:
        results.append(f"Play Store Error: {str(e)}")
        
    return results

def check_visibility(brand_name):
    """
    Aggregates search visibility data.
    """
    # Use DuckDuckGo now
    web_res = get_web_search_results(brand_name)
    
    # Pause briefly to be polite
    time.sleep(1)
    
    app_res = get_app_store_results(brand_name)
    play_res = get_play_store_results(brand_name)
    
    combined_apps = app_res + play_res
    
    # If both lists are empty, add a placeholder so the UI doesn't look broken
    if not web_res:
        web_res = ["No significant web results found."]
    if not combined_apps:
        combined_apps = ["No matching apps found."]
    
    return {
        "google": web_res, # We map 'web' to 'google' key for schema compatibility
        "apps": combined_apps
    }
