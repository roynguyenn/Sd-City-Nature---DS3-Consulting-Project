import { useState, useEffect } from 'react';

interface UseApiReturn<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Custom hook for fetching data from the FastAPI backend
 * @param endpoint - API endpoint path (e.g., "/api/exploratory/observations")
 * @returns Object containing data, loading state, error, and refetch function
 */
export function useApi<T>(endpoint: string): UseApiReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState<number>(0);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const json = await response.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
        console.error('API fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [endpoint, refetchTrigger]);

  const refetch = () => {
    setRefetchTrigger(prev => prev + 1);
  };

  return { data, loading, error, refetch };
}
