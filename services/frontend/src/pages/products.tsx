import { useState, useEffect } from 'react'
import Head from 'next/head'
import { useAuth } from '@/contexts/AuthContext'
import { apiClient, Product } from '@/lib/api'
import ProductList from '../components/ProductList'
import ChatBot from '../components/ChatBot'
import Header from '../components/Header'

export default function ProductsPage() {
  const { user } = useAuth()
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getProducts()
      setProducts(data)
    } catch (error: any) {
      console.error('Failed to fetch products:', error)
      setError(error.message || 'Failed to load products')
    } finally {
      setLoading(false)
    }
  }

  const handleAddToCart = async (productId: string | number) => {
    if (!user) {
      alert('Please login to add items to cart')
      return
    }

    try {
      await apiClient.addToCart(productId.toString(), 1)
      alert('Product added to cart!')
    } catch (error: any) {
      alert(error.message || 'Failed to add to cart')
    }
  }

  return (
    <>
      <Head>
        <title>Products - AI Shopping Mall</title>
        <meta name="description" content="Browse our products" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        <Header />
        
        <main className="container mx-auto px-4 py-8">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              Our Products
            </h1>
            <p className="text-gray-600">
              Browse our collection and find what you need!
            </p>
          </div>

          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Loading products...</p>
            </div>
          ) : (
            <ProductList products={products} onAddToCart={handleAddToCart} />
          )}
        </main>

        {/* AI Chatbot */}
        <ChatBot />
      </div>
    </>
  )
}

// Made with Bob
