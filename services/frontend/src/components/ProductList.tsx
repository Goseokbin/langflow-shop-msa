import { Product } from '@/lib/api'
import { useRouter } from 'next/router'

interface ProductListProps {
  products: Product[]
  onAddToCart: (productId: string | number) => void
}

export default function ProductList({ products, onAddToCart }: ProductListProps) {
  const router = useRouter()

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {products.map((product) => (
        <div
          key={product.id}
          className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow"
        >
          <div
            className="h-48 bg-gray-200 flex items-center justify-center cursor-pointer"
            onClick={() => router.push(`/products/${product.id}`)}
          >
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-gray-400 text-4xl">📦</span>
            )}
          </div>
          
          <div className="p-4">
            <div className="mb-2">
              <span className="text-xs text-blue-600 font-semibold uppercase">
                {product.category}
              </span>
            </div>
            
            <h3
              className="text-lg font-semibold text-gray-900 mb-2 cursor-pointer hover:text-blue-600"
              onClick={() => router.push(`/products/${product.id}`)}
            >
              {product.name}
            </h3>
            
            <p className="text-gray-600 text-sm mb-4 line-clamp-2">
              {product.description}
            </p>
            
            <div className="flex items-center justify-between mb-4">
              <span className="text-2xl font-bold text-blue-600">
                ${typeof product.price === 'number' ? product.price.toFixed(2) : parseFloat(product.price).toFixed(2)}
              </span>
              <span className="text-sm text-gray-500">
                Stock: {product.inventory || product.stock || 0}
              </span>
            </div>
            
            <div className="flex gap-2">
              <button
                onClick={() => router.push(`/products/${product.id}`)}
                className="flex-1 py-2 px-4 rounded-lg font-semibold bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
              >
                View Details
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onAddToCart(product.id)
                }}
                disabled={(product.inventory || product.stock || 0) === 0}
                className={`flex-1 py-2 px-4 rounded-lg font-semibold transition-colors ${
                  (product.inventory || product.stock || 0) > 0
                    ? 'bg-blue-600 text-white hover:bg-blue-700'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                {(product.inventory || product.stock || 0) > 0 ? 'Add to Cart' : 'Out of Stock'}
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// Made with Bob
