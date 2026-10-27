import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '@/contexts/AuthContext'
import { apiClient, Order } from '@/lib/api'
import { useToast } from '@/hooks/useToast'
import Header from '@/components/Header'

export default function OrdersPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancellingOrderId, setCancellingOrderId] = useState<number | null>(null)
  const [deletingAll, setDeletingAll] = useState(false)
  const { success, error: showError, ToastContainer } = useToast()

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
      return
    }

    if (user) {
      loadOrders()
    }
  }, [user, authLoading])

  const loadOrders = async () => {
    try {
      setLoading(true)
      const ordersData = await apiClient.getOrders()
      console.log('📦 Orders loaded:', ordersData)
      console.log('🤖 First order AI summary:', ordersData[0]?.ai_summary)
      setOrders(ordersData)
    } catch (err: any) {
      setError(err.message || 'Failed to load orders')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'processing':
        return 'bg-blue-100 text-blue-800'
      case 'shipped':
        return 'bg-purple-100 text-purple-800'
      case 'delivered':
        return 'bg-green-100 text-green-800'
      case 'cancelled':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const handleCancelOrder = async (orderId: number) => {
    if (!confirm('Are you sure you want to cancel this order? This action cannot be undone.')) {
      return
    }

    try {
      setCancellingOrderId(orderId)
      await apiClient.cancelOrder(orderId.toString())
      success('Order cancelled successfully!')
      // Reload orders
      await loadOrders()
    } catch (err: any) {
      showError(err.message || 'Failed to cancel order')
    } finally {
      setCancellingOrderId(null)
    }
  }

  const canCancelOrder = (status: string) => {
    const lowerStatus = status.toLowerCase()
    return lowerStatus !== 'delivered' && lowerStatus !== 'cancelled'
  }

  const handleDeleteAllOrders = async () => {
    if (!confirm('⚠️ Are you sure you want to delete ALL orders? This action cannot be undone and is for testing purposes only!')) {
      return
    }

    if (!confirm('🚨 FINAL WARNING: This will permanently delete all your order history. Continue?')) {
      return
    }

    try {
      setDeletingAll(true)
      // Delete all orders one by one
      const deletePromises = orders.map(order =>
        apiClient.deleteOrder(order.id.toString()).catch(err => {
          console.error(`Failed to delete order ${order.id}:`, err)
          return null
        })
      )
      
      await Promise.all(deletePromises)
      success('All orders have been deleted!')
      // Reload orders
      await loadOrders()
    } catch (err: any) {
      showError(err.message || 'Failed to delete all orders')
    } finally {
      setDeletingAll(false)
    }
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="text-center">Loading...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">Order History</h1>
          {orders.length > 0 && (
            <button
              onClick={handleDeleteAllOrders}
              disabled={deletingAll}
              className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold text-sm flex items-center gap-2"
            >
              {deletingAll ? (
                <>
                  <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                  Deleting...
                </>
              ) : (
                <>
                  🗑️ Delete All Orders
                </>
              )}
            </button>
          )}
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {orders.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-600 mb-4">You haven't placed any orders yet</p>
            <button
              onClick={() => router.push('/')}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
            >
              Start Shopping
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {orders.map((order) => (
              <div key={order.id} className="bg-white rounded-xl shadow-lg hover:shadow-xl transition-shadow p-6 border border-gray-100">
                <div className="flex justify-between items-start mb-6">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="text-lg font-bold text-gray-800">Order #{String(order.id).substring(0, 8)}</h2>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-semibold uppercase ${getStatusColor(
                          order.status
                        )}`}
                      >
                        {order.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span>📅</span>
                      <p>
                        {new Date(order.created_at).toLocaleDateString('ko-KR', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600 mb-1">Total Amount</p>
                    <p className="text-2xl font-bold text-blue-600">${Number(order.total_amount).toFixed(2)}</p>
                  </div>
                </div>

                {/* AI Summary Section */}
                {order.ai_summary && (
                  <div className="mb-6 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0">
                        <svg
                          className="w-6 h-6 text-purple-600"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                          />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-semibold text-purple-900">AI Order Summary</h3>
                          <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs font-medium rounded-full">
                            Powered by AI
                          </span>
                        </div>
                        <p className="text-gray-700 leading-relaxed">{order.ai_summary}</p>
                      </div>
                    </div>
                  </div>
                )}

                {order.items && order.items.length > 0 ? (
                  <div className="border-t border-gray-200 pt-4">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                      <span>📦</span>
                      <span>Order Items ({order.items.length})</span>
                    </h3>
                    <div className="space-y-3">
                      {order.items.map((item) => (
                        <div key={item.id} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                          {item.product?.image_url && (
                            <img
                              src={item.product.image_url}
                              alt={item.product.name}
                              className="w-20 h-20 object-cover rounded-lg shadow-sm"
                            />
                          )}
                          <div className="flex-1">
                            <p className="font-semibold text-gray-800">{item.product?.name || 'Product'}</p>
                            <p className="text-sm text-gray-600 mt-1">
                              Qty: {item.quantity} × ${Number(item.price).toFixed(2)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-gray-800">
                              ${(item.quantity * Number(item.price)).toFixed(2)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="border-t border-gray-200 pt-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-sm text-blue-800">
                        <span className="font-semibold">Order Summary:</span> {String(order.id).substring(0, 13)}...
                      </p>
                      <p className="text-xs text-blue-600 mt-1">
                        Item details are not available for this order
                      </p>
                    </div>
                  </div>
                )}

                {/* Cancel Order Button */}
                {canCancelOrder(order.status) && (
                  <div className="border-t border-gray-200 pt-4 mt-4">
                    <button
                      onClick={() => handleCancelOrder(order.id)}
                      disabled={cancellingOrderId === order.id}
                      className="w-full bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold"
                    >
                      {cancellingOrderId === order.id ? 'Cancelling...' : 'Cancel Order'}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        
        {/* Toast Notifications */}
        <ToastContainer />
      </div>
    </div>
  )
}

// Made with Bob
