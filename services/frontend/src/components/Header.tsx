import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import { useRouter } from 'next/router'

export default function Header() {
  const { user, logout } = useAuth()
  const router = useRouter()

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  const isActive = (path: string) => router.pathname === path

  return (
    <header className="bg-gradient-to-r from-blue-600 to-blue-700 shadow-lg">
      <nav className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold text-white flex items-center gap-2 hover:opacity-90 transition-opacity">
            <span className="text-3xl">🛍️</span>
            <span>AI Shopping Mall</span>
          </Link>
          
          <div className="flex items-center space-x-2">
            <Link
              href="/"
              className={`px-4 py-2 rounded-lg transition-all ${
                isActive('/')
                  ? 'bg-white text-blue-600 font-semibold'
                  : 'text-white hover:bg-blue-500'
              }`}
            >
              🏠 Home
            </Link>
            {user && (
              <>
                <Link
                  href="/cart"
                  className={`px-4 py-2 rounded-lg transition-all ${
                    isActive('/cart')
                      ? 'bg-white text-blue-600 font-semibold'
                      : 'text-white hover:bg-blue-500'
                  }`}
                >
                  🛒 Cart
                </Link>
                <Link
                  href="/orders"
                  className={`px-4 py-2 rounded-lg transition-all ${
                    isActive('/orders')
                      ? 'bg-white text-blue-600 font-semibold'
                      : 'text-white hover:bg-blue-500'
                  }`}
                >
                  📦 Orders
                </Link>
              </>
            )}
            {user ? (
              <div className="flex items-center space-x-3 ml-4 pl-4 border-l border-blue-400">
                <span className="text-white text-sm">
                  👤 <span className="font-semibold">{user.email}</span>
                </span>
                <button
                  onClick={handleLogout}
                  className="bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition-colors font-medium"
                >
                  Logout
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                className="ml-4 bg-white text-blue-600 px-6 py-2 rounded-lg hover:bg-blue-50 transition-colors font-semibold"
              >
                Login
              </Link>
            )}
          </div>
        </div>
      </nav>
    </header>
  )
}

// Made with Bob
