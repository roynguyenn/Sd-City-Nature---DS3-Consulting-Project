import { useQuery } from '@tanstack/react-query';

interface UseApiReturn<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || '';

export function useApi<T>(endpoint: string): UseApiReturn<T> {
  const { data, isLoading, error, refetch } = useQuery<T>({
    queryKey: [endpoint],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}${endpoint}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    },
  });

  return {
    data: data ?? null,
    loading: isLoading,
    error: error ? (error instanceof Error ? error.message : 'An error occurred') : null,
    refetch,
  };
}