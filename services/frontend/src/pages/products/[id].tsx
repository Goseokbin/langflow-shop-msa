import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import Head from 'next/head'
import { useAuth } from '@/contexts/AuthContext'
import { apiClient, Product } from '@/lib/api'
import { useToast } from '@/hooks/useToast'
import Header from '@/components/Header'

export default function ProductDetailPage() {
  const router = useRouter()
  const { id } = router.query
  const { user } = useAuth()
  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [quantity, setQuantity] = useState(1)
  const { success, error: showError, warning, ToastContainer } = useToast()

  useEffect(() => {
    if (id) {
      fetchProduct()
    }
  }, [id])

  const fetchProduct = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getProduct(id as string)
      setProduct(data)
    } catch (error: any) {
      console.error('Failed to fetch product:', error)
      setError(error.message || 'Failed to load product')
    } finally {
      setLoading(false)
    }
  }

  const handleAddToCart = async () => {
    if (!user) {
      warning('Please login to add items to cart')
      setTimeout(() => router.push('/login'), 1500)
      return
    }

    try {
      await apiClient.addToCart(id as string, quantity)
      success(`Added ${quantity} item(s) to cart!`)
    } catch (error: any) {
      showError(error.message || 'Failed to add to cart')
    }
  }

  const parseSpecifications = (specs: string | undefined) => {
    if (!specs) return {}
    try {
      return JSON.parse(specs)
    } catch {
      return {}
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading product...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error || 'Product not found'}
          </div>
          <button
            onClick={() => router.push('/')}
            className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
            Back to Products
          </button>
        </div>
      </div>
    )
  }

  const specifications = parseSpecifications(product.specifications)
  const price = typeof product.price === 'number' ? product.price : parseFloat(product.price)

  return (
    <>
      <Head>
        <title>{product.name} - AI Shopping Mall</title>
        <meta name="description" content={product.description} />
      </Head>

      <div className="min-h-screen bg-gray-50">
        <Header />
        
        <main className="container mx-auto px-4 py-8">
          {/* Breadcrumb */}
          <div className="mb-6 text-sm text-gray-600">
            <button onClick={() => router.push('/')} className="hover:text-blue-600">
              Home
            </button>
            <span className="mx-2">/</span>
            <button onClick={() => router.push('/')} className="hover:text-blue-600">
              {product.category}
            </button>
            <span className="mx-2">/</span>
            <span className="text-gray-900">{product.name}</span>
          </div>

          <div className="bg-white rounded-xl shadow-lg overflow-hidden">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 p-8">
              {/* Product Image */}
              <div className="flex items-center justify-center bg-gray-100 rounded-lg p-8">
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="max-w-full max-h-96 object-contain"
                  />
                ) : (
                  <div className="w-full h-96 flex items-center justify-center text-gray-400">
                    <span className="text-6xl">📦</span>
                  </div>
                )}
              </div>

              {/* Product Info */}
              <div className="flex flex-col">
                {product.brand && (
                  <p className="text-sm text-blue-600 font-semibold mb-2">{product.brand}</p>
                )}
                <h1 className="text-3xl font-bold text-gray-900 mb-4">{product.name}</h1>
                
                {/* Rating */}
                {product.rating && (
                  <div className="flex items-center gap-2 mb-4">
                    <div className="flex items-center">
                      {[...Array(5)].map((_, i) => (
                        <span
                          key={i}
                          className={`text-xl ${
                            i < Math.floor(Number(product.rating) || 0) ? 'text-yellow-400' : 'text-gray-300'
                          }`}
                        >
                          ★
                        </span>
                      ))}
                    </div>
                    <span className="text-gray-600">
                      {Number(product.rating).toFixed(1)} ({product.review_count} reviews)
                    </span>
                  </div>
                )}

                {/* Price */}
                <div className="mb-6">
                  <p className="text-4xl font-bold text-blue-600">${price.toFixed(2)}</p>
                  {product.inventory !== undefined && (
                    <p className="text-sm text-gray-600 mt-2">
                      {product.inventory > 0 ? (
                        <span className="text-green-600">In Stock ({product.inventory} available)</span>
                      ) : (
                        <span className="text-red-600">Out of Stock</span>
                      )}
                    </p>
                  )}
                </div>

                {/* Short Description */}
                <p className="text-gray-700 mb-6">{product.description}</p>

                {/* Quantity Selector */}
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Quantity
                  </label>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="bg-gray-200 px-4 py-2 rounded-lg hover:bg-gray-300 font-semibold"
                    >
                      -
                    </button>
                    <span className="px-6 py-2 bg-gray-100 rounded-lg font-semibold min-w-[60px] text-center">
                      {quantity}
                    </span>
                    <button
                      onClick={() => setQuantity(quantity + 1)}
                      className="bg-gray-200 px-4 py-2 rounded-lg hover:bg-gray-300 font-semibold"
                    >
                      +
                    </button>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-4 mb-6">
                  <button
                    onClick={handleAddToCart}
                    disabled={!product.inventory || product.inventory === 0}
                    className="flex-1 bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold text-lg"
                  >
                    Add to Cart
                  </button>
                  <button
                    onClick={() => router.push('/cart')}
                    className="px-6 py-3 border-2 border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 font-semibold"
                  >
                    View Cart
                  </button>
                </div>

                {/* Category Badge */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">Category:</span>
                  <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium">
                    {product.category}
                  </span>
                </div>
              </div>
            </div>

            {/* Detailed Description */}
            {product.detailed_description && (
              <div className="border-t border-gray-200 p-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Product Details</h2>
                <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                  {product.detailed_description}
                </p>
              </div>
            )}

            {/* Specifications */}
            {Object.keys(specifications).length > 0 && (
              <div className="border-t border-gray-200 p-8 bg-gray-50">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Specifications</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(specifications).map(([key, value]) => (
                    <div key={key} className="flex justify-between py-2 border-b border-gray-200">
                      <span className="font-semibold text-gray-700">{key}:</span>
                      <span className="text-gray-600">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Toast Notifications */}
        <ToastContainer />
      </div>
    </>
  )
}

// Made with Bob
