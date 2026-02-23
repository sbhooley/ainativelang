from fastapi import FastAPI
app = FastAPI()

@app.get('/scrape/products')
def get_scrape_products():
    # Exec ->L1
    return {"data": []}

@app.get('/scrape/prices')
def get_scrape_prices():
    # Exec ->L2
    return {"data": []}

