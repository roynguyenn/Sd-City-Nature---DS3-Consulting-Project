import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { ExploratoryAnalysis } from './pages/ExploratoryAnalysis';
import { CityComparison } from './pages/CityComparison';
import { StrategyRecommendations } from './pages/StrategyRecommendations';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10 * 60 * 1000,    // data stays fresh for 10 minutes
      gcTime: 30 * 60 * 1000,       // cache kept for 30 minutes
      refetchOnWindowFocus: false,   // don't refetch when switching browser tabs
      retry: 1,                      // only retry once on failure
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<ExploratoryAnalysis />} />
            <Route path="comparison" element={<CityComparison />} />
            <Route path="strategy" element={<StrategyRecommendations />} />
          </Route>
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}

export default App;