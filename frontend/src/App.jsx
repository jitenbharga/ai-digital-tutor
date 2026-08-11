import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { useAuth } from './context/AuthContext';
import { PreferencesProvider } from './context/PreferencesContext';
import { CelebrationProvider } from './components/CelebrationManager';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

// PERF: route-level code splitting. Each page (and its heavy deps like KaTeX
// and the force-graph) is fetched only when its route is visited, cutting the
// initial JS bundle dramatically. Auth screens are kept small; everything
// behind the app shell is lazy.
const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const Landing = lazy(() => import('./pages/Landing'));
const Home = lazy(() => import('./pages/Home'));
const TopicSelect = lazy(() => import('./pages/TopicSelect'));
const Tutor = lazy(() => import('./pages/Tutor'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Review = lazy(() => import('./pages/Review'));
const Settings = lazy(() => import('./pages/Settings'));
const GuardianDashboard = lazy(() => import('./pages/GuardianDashboard'));
const Profile = lazy(() => import('./pages/Profile'));
const Quiz = lazy(() => import('./pages/Quiz'));
const Onboarding = lazy(() => import('./pages/Onboarding'));
const MyPath = lazy(() => import('./pages/MyPath'));
const Ask = lazy(() => import('./pages/Ask'));
const CurriculumMap = lazy(() => import('./pages/CurriculumMap'));
const MistakesNotebook = lazy(() => import('./pages/MistakesNotebook'));
const Notebook = lazy(() => import('./pages/Notebook'));
const DailySession = lazy(() => import('./pages/DailySession'));
const CodePractice = lazy(() => import('./pages/CodePractice'));
const Flashcards = lazy(() => import('./pages/Flashcards'));
const ExamPlan = lazy(() => import('./pages/ExamPlan'));
const Materials = lazy(() => import('./pages/Materials'));
const Feynman = lazy(() => import('./pages/Feynman'));
const SolutionCheck = lazy(() => import('./pages/SolutionCheck'));
const StepSolver = lazy(() => import('./pages/StepSolver'));
const CheatSheet = lazy(() => import('./pages/CheatSheet'));

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-screen" role="status" aria-label="Loading">
      <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <PageFallback />;
  return user ? children : <Navigate to="/welcome" />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
    <ErrorBoundary>
    <Suspense fallback={<PageFallback />}>
    <Routes>
      <Route path="/welcome" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
      <Route path="/" element={<ProtectedRoute><PreferencesProvider><CelebrationProvider><Layout /></CelebrationProvider></PreferencesProvider></ProtectedRoute>}>
        <Route index element={<ErrorBoundary><Home /></ErrorBoundary>} />
        <Route path="learn" element={<ErrorBoundary><TopicSelect /></ErrorBoundary>} />
        <Route path="tutor" element={<ErrorBoundary><Tutor /></ErrorBoundary>} />
        <Route path="ask" element={<ErrorBoundary><Ask /></ErrorBoundary>} />
        <Route path="curriculum/:subject" element={<ErrorBoundary><CurriculumMap /></ErrorBoundary>} />
        <Route path="review" element={<ErrorBoundary><Review /></ErrorBoundary>} />
        <Route path="mistakes" element={<ErrorBoundary><MistakesNotebook /></ErrorBoundary>} />
        <Route path="notebook" element={<ErrorBoundary><Notebook /></ErrorBoundary>} />
        <Route path="session" element={<ErrorBoundary><DailySession /></ErrorBoundary>} />
        <Route path="practice" element={<ErrorBoundary><CodePractice /></ErrorBoundary>} />
        <Route path="flashcards" element={<ErrorBoundary><Flashcards /></ErrorBoundary>} />
        <Route path="exam-plan" element={<ErrorBoundary><ExamPlan /></ErrorBoundary>} />
        <Route path="materials" element={<ErrorBoundary><Materials /></ErrorBoundary>} />
        <Route path="feynman" element={<ErrorBoundary><Feynman /></ErrorBoundary>} />
        <Route path="solve" element={<ErrorBoundary><SolutionCheck /></ErrorBoundary>} />
        <Route path="solver" element={<ErrorBoundary><StepSolver /></ErrorBoundary>} />
        <Route path="cheatsheet" element={<ErrorBoundary><CheatSheet /></ErrorBoundary>} />
        <Route path="progress" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<ErrorBoundary><Profile /></ErrorBoundary>} />
        {/* Legacy routes — redirect to new tabs */}
        <Route path="dashboard" element={<Navigate to="/progress" replace />} />
        <Route path="quiz" element={<Quiz />} />
        <Route path="path" element={<MyPath />} />
        <Route path="guardian" element={<GuardianDashboard />} />
      </Route>
    </Routes>
    </Suspense>
    </ErrorBoundary>
    </QueryClientProvider>
  );
}
