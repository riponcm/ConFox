import { createBrowserRouter, Navigate } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import Shell from './components/Shell.tsx'
import Ask from './pages/Ask.tsx'
import Brief from './pages/Brief.tsx'
import CatchUp from './pages/CatchUp.tsx'
import Dashboard from './pages/Dashboard.tsx'
import Now from './pages/Now.tsx'
import People from './pages/People.tsx'
import Schedule from './pages/Schedule.tsx'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'now', element: <Now /> },
      { path: 'schedule', element: <Schedule /> },
      { path: 'people', element: <People /> },
      { path: 'ask', element: <Ask /> },
      { path: 'brief', element: <Brief /> },
      { path: 'catch-up', element: <CatchUp /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
