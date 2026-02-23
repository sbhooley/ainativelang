const { useState, useEffect } = React;

const API_BASE = '/api';
const CART_KEY = 'ecom_cart';

function useProducts() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetch(API_BASE + '/products')
      .then(r => r.json())
      .then(d => { setProducts(Array.isArray(d.data) ? d.data : (d.products || [])); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);
  return { products, loading, error };
}

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (_) { return []; }
}

function saveCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
}

const Nav = ({ path, setPath, cartCount }) => (
  <nav className="nav">
    <a className={"nav-link" + (path === '/' ? ' active' : '')} href="#/" onClick={e => { e.preventDefault(); setPath('/'); }}>Home</a>
    <a className={"nav-link" + (path === '/products' ? ' active' : '')} href="#/products" onClick={e => { e.preventDefault(); setPath('/products'); }}>Shop</a>
    <a className="nav-link nav-cart" href="#/cart" onClick={e => { e.preventDefault(); setPath('/cart'); }}>
      Cart {cartCount > 0 ? <span className="cart-badge">{cartCount}</span> : null}
    </a>
  </nav>
);

const Header = () => (
  <header className="header">
    <h1 className="logo"><a href="#/">Store</a></h1>
  </header>
);

const ProductCard = ({ product, onAddToCart }) => (
  <article className="product-card">
    <div className="product-card__image">
      <span className="product-card__placeholder">{(product.name || '?').slice(0, 1)}</span>
    </div>
    <div className="product-card__body">
      <h3 className="product-card__name">{product.name || 'Product'}</h3>
      <p className="product-card__sku">{product.sku || ''}</p>
      <p className="product-card__price">${Number(product.price ?? 0).toFixed(2)}</p>
      <button type="button" className="btn btn-primary product-card__btn" onClick={() => onAddToCart(product)}>
        Add to cart
      </button>
    </div>
  </article>
);

const ProductGrid = ({ products, onAddToCart, loading, error }) => {
  if (loading) return <div className="page-section"><p className="muted">Loading products…</p></div>;
  if (error) return <div className="page-section"><p className="error">Failed to load: {error}</p></div>;
  if (!products.length) return <div className="page-section"><p className="muted">No products yet.</p></div>;
  return (
    <div className="product-grid">
      {products.map(p => <ProductCard key={p.id ?? p.sku ?? p.name} product={p} onAddToCart={onAddToCart} />)}
    </div>
  );
};

const CartItem = ({ item, onUpdateQty, onRemove }) => (
  <div className="cart-item">
    <div className="cart-item__info">
      <span className="cart-item__name">{item.name}</span>
      <span className="cart-item__price">${Number(item.price || 0).toFixed(2)}</span>
    </div>
    <div className="cart-item__actions">
      <input type="number" min="1" value={item.qty} onChange={e => onUpdateQty(item, parseInt(e.target.value, 10) || 1)} className="cart-item__qty" />
      <button type="button" className="btn btn-ghost" onClick={() => onRemove(item)}>Remove</button>
    </div>
  </div>
);

const CartPage = ({ cart, onUpdateQty, onRemove, setPath }) => {
  const total = cart.reduce((s, i) => s + (Number(i.price) || 0) * (i.qty || 1), 0);
  return (
    <div className="page-section">
      <h2 className="page-title">Your cart</h2>
      {cart.length === 0 ? (
        <p className="muted">Cart is empty. <a href="#/products" onClick={e => { e.preventDefault(); setPath('/products'); }}>Browse products</a></p>
      ) : (
        <>
          <div className="cart-list">
            {cart.map((item, i) => <CartItem key={item.id + '-' + i} item={item} onUpdateQty={onUpdateQty} onRemove={onRemove} />)}
          </div>
          <div className="cart-footer">
            <p className="cart-total">Total: <strong>${total.toFixed(2)}</strong></p>
            <button type="button" className="btn btn-primary" onClick={() => setPath('/checkout')}>Proceed to checkout</button>
          </div>
        </>
      )}
    </div>
  );
};

const CheckoutPage = ({ cart, setPath }) => {
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const total = cart.reduce((s, i) => s + (Number(i.price) || 0) * (i.qty || 1), 0);

  const handlePlaceOrder = () => {
    setSubmitting(true);
    fetch(API_BASE + '/checkout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items: cart, total }) })
      .then(r => r.json())
      .then(() => { setDone(true); saveCart([]); })
      .catch(() => {})
      .finally(() => setSubmitting(false));
  };

  if (done) {
    return (
      <div className="page-section">
        <h2 className="page-title">Order received</h2>
        <p className="muted">Thank you. Your order has been submitted.</p>
        <button type="button" className="btn btn-primary" onClick={() => setPath('/')}>Back to home</button>
      </div>
    );
  }

  return (
    <div className="page-section">
      <h2 className="page-title">Checkout</h2>
      <div className="checkout-summary">
        <p><strong>{cart.length}</strong> item(s)</p>
        <p className="cart-total">Total: <strong>${total.toFixed(2)}</strong></p>
      </div>
      <button type="button" className="btn btn-primary" disabled={submitting || cart.length === 0} onClick={handlePlaceOrder}>
        {submitting ? 'Placing order…' : 'Place order'}
      </button>
    </div>
  );
};

const App = () => {
  const [path, setPath] = useState(() => (window.location.hash || '#/').slice(1) || '/');
  const [cart, setCart] = useState(loadCart);
  const { products, loading, error } = useProducts();

  useEffect(() => { const onHash = () => setPath((window.location.hash || '#/').slice(1) || '/'); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  useEffect(() => { saveCart(cart); }, [cart]);

  const addToCart = (product) => {
    const id = product.id ?? product.sku ?? product.name;
    const existing = cart.find(i => (i.id ?? i.sku ?? i.name) === id);
    if (existing) setCart(cart.map(i => i === existing ? { ...i, qty: (i.qty || 1) + 1 } : i));
    else setCart([...cart, { ...product, qty: 1 }]);
  };

  const updateQty = (item, qty) => {
    if (qty < 1) return setCart(cart.filter(i => i !== item));
    setCart(cart.map(i => i === item ? { ...i, qty } : i));
  };

  const removeFromCart = (item) => setCart(cart.filter(i => i !== item));

  const cartCount = cart.reduce((s, i) => s + (i.qty || 1), 0);

  const Page = path === '/cart' ? () => <CartPage cart={cart} onUpdateQty={updateQty} onRemove={removeFromCart} setPath={setPath} />
    : path === '/checkout' ? () => <CheckoutPage cart={cart} setPath={setPath} />
    : () => <ProductGrid products={products} onAddToCart={addToCart} loading={loading} error={error} />;

  return (
    <div className="app">
      <Header />
      <Nav path={path} setPath={setPath} cartCount={cartCount} />
      <main className="main">
        <Page />
      </main>
    </div>
  );
};

ReactDOM.render(<App />, document.getElementById('root'));
