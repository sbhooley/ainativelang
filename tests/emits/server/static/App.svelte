<script>
  import { onMount } from 'svelte';
  let path = typeof location !== 'undefined' ? (location.hash || '#/').slice(1) || '/' : '/';
  const R = {"/": "Dashboard", "/products": "ProductList", "/orders": "OrderTable", "/customers": "CustomerTable"}
  let products = [];
  let product = [];
  let orders = [];
  let order = [];
  let ord = [];
  let customers = [];
  onMount(() => {
    fetch('/api/products', { method: 'GET' }).then(r => r.json()).then(d => { products = d.data || [] });
    fetch('/api/product', { method: 'GET' }).then(r => r.json()).then(d => { product = d.data || [] });
    fetch('/api/orders', { method: 'GET' }).then(r => r.json()).then(d => { orders = d.data || [] });
    fetch('/api/order', { method: 'GET' }).then(r => r.json()).then(d => { order = d.data || [] });
    fetch('/api/checkout', { method: 'POST' }).then(r => r.json()).then(d => { ord = d.data || [] });
    fetch('/api/customers', { method: 'GET' }).then(r => r.json()).then(d => { customers = d.data || [] });
  });
</script>
<svelte:window on:hashchange={() => path = (location.hash || '#/').slice(1) || '/'} />
<nav>{#each Object.keys(R) as p}<a href="#{p}">{p}</a>{/each}</nav>
{#if path === '/'}<div class="dashboard"><h1>Dashboard</h1><pre>{JSON.stringify(products, null, 2)}</pre></div>{/if}
{#if path === '/products'}<div class="dashboard"><h1>ProductList</h1><pre>{JSON.stringify(products, null, 2)}</pre></div>{/if}
{#if path === '/orders'}<div class="dashboard"><h1>OrderTable</h1><pre>{JSON.stringify(orders, null, 2)}</pre></div>{/if}
{#if path === '/customers'}<div class="dashboard"><h1>CustomerTable</h1><pre>{JSON.stringify(products, null, 2)}</pre></div>{/if}