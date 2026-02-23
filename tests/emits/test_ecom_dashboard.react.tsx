// AINL emitted React/TSX
import React, { useState } from 'react';

export const Dashboard: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  return (
    <div className="dashboard">
      <h1>Dashboard</h1>
    </div>
  );
};

export const ProductList: React.FC = () => {
  const [data, setData] = useState<any>(null);
  return (
    <div className="dashboard">
      <h1>ProductList</h1>
      <DataTable data={products} />
    </div>
  );
};

export const OrderTable: React.FC = () => {
  const [data, setData] = useState<any>(null);
  return (
    <div className="dashboard">
      <h1>OrderTable</h1>
      <DataTable data={orders} />
    </div>
  );
};

export const CheckoutBtn: React.FC = () => {
  const [data, setData] = useState<any>(null);
  return (
    <div className="dashboard">
      <h1>CheckoutBtn</h1>
    </div>
  );
};

