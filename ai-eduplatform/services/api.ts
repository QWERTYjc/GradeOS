import axios from 'axios';

// Create a standard axios instance
// The mock adapter will intercept requests made via this instance
export const api = axios.create({
  baseURL: '/api', // This is virtual, intercepted by mock
  timeout: 1000,
});

// Helper to simulate network delay for realism
export const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));