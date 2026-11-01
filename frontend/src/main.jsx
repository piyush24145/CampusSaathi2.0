import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import AuthPage from './components/AuthPage.jsx'
import { getCurrentUser, clearAuth, isLoggedIn } from './services/api.js'

function Root() {
  const [currentUser, setCurrentUser] = useState(() =>
    isLoggedIn() ? getCurrentUser() : null
  );

  function handleLogout() {
    clearAuth();
    setCurrentUser(null);
  }

  if (!currentUser) {
    return <AuthPage onAuthSuccess={(user) => setCurrentUser(user)} />;
  }

  return <App currentUser={currentUser} onLogout={handleLogout} />;
}

createRoot(document.getElementById('root')).render(<Root />)
