import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30s before refetch
      gcTime: 5 * 60_000,       // 5m cache retention
      retry: 1,                 // 1 retry on failure
      refetchOnWindowFocus: false,
    },
  },
});
