import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AskPage } from './pages/AskPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { LoginPage } from './pages/LoginPage'
import { ModelsPage } from './pages/ModelsPage'
import { SetupPage } from './pages/SetupPage'

function App() {
    return (
        <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/" element={<Layout />}>
                <Route index element={<AskPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="models" element={<ModelsPage />} />
            </Route>
        </Routes>
    )
}

export default App
