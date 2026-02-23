<script setup>
import { ref, onMounted } from 'vue'
const path = ref(typeof location !== 'undefined' ? (location.hash || '#/').slice(1) || '/' : '/')
const R = {"/": "Dashboard", "/products": "ProductList", "/orders": "OrderTable", "/customers": "CustomerTable"}
const nav = Object.keys(R)
const products = ref([])
onMounted(() => fetch('/api/products', { method: 'GET' }).then(r => r.json()).then(d => { products.value = d.data || [] }))
const product = ref([])
onMounted(() => fetch('/api/product', { method: 'GET' }).then(r => r.json()).then(d => { product.value = d.data || [] }))
const orders = ref([])
onMounted(() => fetch('/api/orders', { method: 'GET' }).then(r => r.json()).then(d => { orders.value = d.data || [] }))
const order = ref([])
onMounted(() => fetch('/api/order', { method: 'GET' }).then(r => r.json()).then(d => { order.value = d.data || [] }))
const ord = ref([])
onMounted(() => fetch('/api/checkout', { method: 'POST' }).then(r => r.json()).then(d => { ord.value = d.data || [] }))
const customers = ref([])
onMounted(() => fetch('/api/customers', { method: 'GET' }).then(r => r.json()).then(d => { customers.value = d.data || [] }))
</script>
<template>
  <nav><a v-for="p in nav" :key="p" :href="'#'+p">{{ p }}</a></nav>
  <div v-if="path === '/'" class="dashboard">
    <h1>Dashboard</h1>
    <pre>{{ JSON.stringify(products, null, 2) }}</pre>
  </div>
  <div v-if="path === '/products'" class="dashboard">
    <h1>ProductList</h1>
    <pre>{{ JSON.stringify(products, null, 2) }}</pre>
  </div>
  <div v-if="path === '/orders'" class="dashboard">
    <h1>OrderTable</h1>
    <pre>{{ JSON.stringify(orders, null, 2) }}</pre>
  </div>
  <div v-if="path === '/customers'" class="dashboard">
    <h1>CustomerTable</h1>
    <pre>{{ JSON.stringify(products, null, 2) }}</pre>
  </div>
</template>