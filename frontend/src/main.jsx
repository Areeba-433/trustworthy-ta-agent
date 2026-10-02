import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
    <BrowserRouter>
            <AuthProvider>
      <App />
                <Toaster
                    position="top-center"
                    toastOptions={{
                        style: {
                            background: '#fff',
                            color: '#1e293b',
                            border: '1px solid #e2e8f0',
                            fontSize: '14px',
                            borderRadius: '12px',
                            boxShadow: '0 10px 30px rgba(15,23,42,0.08)',
                        },
                        success: { iconTheme: { primary: '#4f46e5', secondary: '#fff' } },
                        error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
                    }}
                />
            </AuthProvider>
    </BrowserRouter>
    </React.StrictMode>,
)