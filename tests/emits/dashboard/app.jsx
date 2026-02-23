const { useState, useEffect } = React;

const DataTable = ({ data, columns }) => (
  <table><tbody>{((data || []).map((row, i) => {
    const isObj = row && typeof row === 'object' && !Array.isArray(row);
    const cols = columns || (isObj ? Object.keys(row) : ['value']);
    return <tr key={i}>{cols.map(c => <td key={c}>{isObj ? row[c] : String(row)}</td>)}</tr>;
  }))}</tbody></table>
);

const DataForm = ({ name, fields, onSubmit }) => (
  <form onSubmit={e => { e.preventDefault(); onSubmit(new FormData(e.target)); }}>
    { (fields || []).map(f => <label key={f}>{f}<input name={f} /></label>) }
    <button type="submit">Submit</button>
  </form>
);

const Dashboard = () => {
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  return (
    <div className="dashboard">
      <h1>Dashboard</h1>
    </div>
  );
};

const ProductList = () => {
  const [data, setData] = useState(null);
  const [products, setProducts] = useState(null);
  return (
    <div className="dashboard">
      <h1>ProductList</h1>
      <DataTable data={products} columns={["id", "name", "price", "sku"]} />
    </div>
  );
};

const OrderTable = () => {
  const [data, setData] = useState(null);
  const [orders, setOrders] = useState(null);
  return (
    <div className="dashboard">
      <h1>OrderTable</h1>
      <DataTable data={orders} columns={["id", "uid", "total", "status"]} />
    </div>
  );
};

const CustomerTable = () => {
  const [data, setData] = useState(null);
  const [customers, setCustomers] = useState(null);
  return (
    <div className="dashboard">
      <h1>CustomerTable</h1>
      <DataTable data={customers} columns={["id", "email", "name"]} />
    </div>
  );
};

const CheckoutBtn = () => {
  const [data, setData] = useState(null);
  return (
    <div className="dashboard">
      <h1>CheckoutBtn</h1>
      <button onClick={ () => fetch('/api/checkout', { method: 'POST' }).then(r => r.json()).then(console.log) }>CheckoutBtn</button>
    </div>
  );
};

const Shell = ({ children }) => (
  <div className="layout"><aside>Nav</aside><main>{children}</main></div>
);

const App = () => {
  const [path, setPath] = useState(() => (window.location.hash || '#/').slice(1) || '/');
  useEffect(() => { const onHash = () => setPath((window.location.hash || '#/').slice(1) || '/'); window.addEventListener('hashchange', onHash); onHash(); return () => window.removeEventListener('hashchange', onHash); }, []);
  const R = {"/": "Dashboard", "/products": "ProductList", "/orders": "OrderTable", "/customers": "CustomerTable"};
  const Comps = { "Dashboard": Dashboard, "ProductList": ProductList, "OrderTable": OrderTable, "CustomerTable": CustomerTable, "CheckoutBtn": CheckoutBtn };
  const Page = Comps[R[path]] || Dashboard;
  const nav = ["/", "/products", "/orders", "/customers"].map(p => <a key={p} href={'#'+p}>{p}</a>);
  return <Shell><nav>{nav}</nav><main><Page /></main></Shell>;
};

ReactDOM.render(<App />, document.getElementById('root'));
