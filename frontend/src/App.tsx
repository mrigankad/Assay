import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AskPage } from './pages/AskPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { LoginPage } from './pages/LoginPage'
import { ModelsPage } from './pages/ModelsPage'
import { SetupPage } from './pages/SetupPage'
import { AuthCallbackPage } from './pages/AuthCallbackPage'
import { AuditPage } from './pages/AuditPage'
import { MatrixPage } from './pages/MatrixPage'
import { EvalsPage } from './pages/EvalsPage'
import { SettingsPage } from './pages/SettingsPage'

function App() {
    return (
        <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="/" element={<Layout />}>
                <Route index element={<AskPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="models" element={<ModelsPage />} />
                <Route path="matrix" element={<MatrixPage />} />
                <Route path="evals" element={<EvalsPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="settings" element={<SettingsPage />} />
            </Route>
        </Routes>
    )
}

export default App
