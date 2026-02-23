from fastapi import FastAPI
app = FastAPI()

@app.get('/products')
def get_products():
    # Exec ->L1
    return {"data": []}

@app.post('/products')
def post_products():
    # Exec ->L7
    return {"data": []}

@app.get('/product')
def get_product():
    # Exec ->L6
    return {"data": []}

@app.get('/orders')
def get_orders():
    # Exec ->L2
    return {"data": []}

@app.post('/orders')
def post_orders():
    # Exec ->L9
    return {"data": []}

@app.get('/order')
def get_order():
    # Exec ->L8
    return {"data": []}

@app.post('/checkout')
def post_checkout():
    # Exec ->L3
    return {"data": []}

@app.get('/customers')
def get_customers():
    # Exec ->L10
    return {"data": []}

