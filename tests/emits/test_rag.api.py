from fastapi import FastAPI
app = FastAPI()

@app.get('/products')
def get_products():
    # Exec ->L1
    return {"data": []}

@app.get('/orders')
def get_orders():
    # Exec ->L2
    return {"data": []}

@app.post('/checkout')
def post_checkout():
    # Exec ->L3
    return {"data": []}

@app.get('/tick')
def get_tick():
    # Exec ->L->OnTick
    return {"data": []}

