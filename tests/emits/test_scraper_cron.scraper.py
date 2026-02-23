import requests
from bs4 import BeautifulSoup

def scrape_products():
    resp = requests.get('https://example.com/products')
    soup = BeautifulSoup(resp.text, 'html.parser')
    el = soup.select_one('.product')
    list = el.get_text(strip=True) if el else None
    el = soup.select_one('h2')
    title = el.get_text(strip=True) if el else None
    el = soup.select_one('.price')
    price = el.get_text(strip=True) if el else None
    return { 'list': list, 'title': title, 'price': price }

def scrape_prices():
    resp = requests.get('https://prices.example.com')
    soup = BeautifulSoup(resp.text, 'html.parser')
    el = soup.select_one('')
    table = el.get_text(strip=True) if el else None
    return { 'table': table }

