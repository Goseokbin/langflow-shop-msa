// API Client for backend services
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

interface ApiError {
  message: string
  status: number
}

// Types
export interface User {
  id: number
  email: string
  username: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Product {
  id: string
  name: string
  description: string
  price: number | string
  stock?: number
  inventory?: number
  category: string
  image_url?: string
  detailed_description?: string
  specifications?: string
  brand?: string
  rating?: number
  review_count?: number
}

export interface CartItem {
  id: number
  product_id: number
  quantity: number
  product?: Product
}

export interface Cart {
  id: number
  user_id: number
  items: CartItem[]
}

export interface OrderItem {
  id: number
  product_id: number
  quantity: number
  price: number
  product?: Product
}

export interface Order {
  id: number
  user_id: number
  total_amount: number
  status: string
  created_at: string
  items: OrderItem[]
  ai_summary?: string
}

class ApiClient {
  private token: string | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('token')
    }
  }

  setToken(token: string | null) {
    this.token = token
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('token', token)
      } else {
        localStorage.removeItem('token')
      }
    }
  }

  getToken() {
    return this.token
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const error: ApiError = {
        message: await response.text(),
        status: response.status,
      }
      throw error
    }

    return response.json()
  }

  // Auth endpoints
  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email,
        password,
      }),
    })

    if (!response.ok) {
      throw new Error('Login failed')
    }

    const data = await response.json()
    this.setToken(data.access_token)
    return data
  }

  async register(email: string, password: string, fullName: string) {
    return this.request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        name: fullName,
      }),
    })
  }

  async getCurrentUser(): Promise<User> {
    return this.request('/api/users/me', {
      method: 'GET',
    })
  }

  logout() {
    this.setToken(null)
  }

  // Product endpoints
  async getProducts(): Promise<Product[]> {
    return this.request('/api/products', {
      method: 'GET',
    })
  }

  async getProduct(id: string): Promise<Product> {
    return this.request(`/api/products/${id}`, {
      method: 'GET',
    })
  }

  // Cart endpoints
  async getCart(): Promise<Cart> {
    return this.request('/api/cart', {
      method: 'GET',
    })
  }

  async addToCart(productId: string, quantity: number = 1) {
    return this.request('/api/cart/items', {
      method: 'POST',
      body: JSON.stringify({
        product_id: productId,
        quantity,
      }),
    })
  }

  async updateCartItem(itemId: string, quantity: number) {
    return this.request(`/api/cart/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify({ quantity }),
    })
  }

  async removeFromCart(itemId: string) {
    return this.request(`/api/cart/items/${itemId}`, {
      method: 'DELETE',
    })
  }

  async clearCart() {
    return this.request('/api/cart/clear', {
      method: 'DELETE',
    })
  }

  // Order endpoints
  async createOrder(shippingAddress: string = '123 Main St') {
    return this.request('/api/orders', {
      method: 'POST',
      body: JSON.stringify({
        shipping_address: shippingAddress,
      }),
    })
  }

  async getOrders(): Promise<Order[]> {
    return this.request('/api/orders', {
      method: 'GET',
    })
  }

  async getOrder(id: string): Promise<Order> {
    return this.request(`/api/orders/${id}`, {
      method: 'GET',
    })
  }

  async cancelOrder(id: string) {
    return this.request(`/api/orders/${id}/cancel`, {
      method: 'POST',
    })
  }

  async deleteOrder(id: string) {
    return this.request(`/api/orders/${id}`, {
      method: 'DELETE',
    })
  }
}

export const apiClient = new ApiClient()

export const api = new ApiClient()
export default api

// Made with Bob
