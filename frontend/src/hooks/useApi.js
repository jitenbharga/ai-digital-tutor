/**
 * React Query hooks wrapping common API calls.
 *
 * Usage:
 *   const { data, isLoading } = useProgress(studentId);
 *   const { data: subjects } = useSubjects();
 *   const { mutate: submitAnswer } = useSubmitAnswer();
 *
 * Replaces raw fetch + useEffect patterns with automatic
 * caching, deduplication, and stale-while-revalidate.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

// ── Queries (GET) ──

export function useSubjects() {
  return useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.getSubjects(),
    staleTime: 60_000,
  });
}

export function useCurriculum(subject) {
  return useQuery({
    queryKey: ['curriculum', subject],
    queryFn: () => api.getCurriculum(subject),
    enabled: !!subject,
  });
}

export function useProgress(studentId) {
  return useQuery({
    queryKey: ['progress', studentId],
    queryFn: () => api.progress(studentId),
    enabled: !!studentId,
  });
}

export function useGamification() {
  return useQuery({
    queryKey: ['gamification'],
    queryFn: () => api.myGamification(),
    staleTime: 30_000,
  });
}

export function useQuests() {
  return useQuery({
    queryKey: ['quests'],
    queryFn: () => api.myQuests(),
    staleTime: 30_000,
  });
}

export function useReviewDueCount() {
  return useQuery({
    queryKey: ['reviewDueCount'],
    queryFn: () => api.getReviewDueCount(),
    staleTime: 60_000,
  });
}

export function useToday() {
  return useQuery({
    queryKey: ['today'],
    queryFn: () => api.getToday(),
    staleTime: 30_000,
  });
}

export function useMasteryHistory() {
  return useQuery({
    queryKey: ['masteryHistory'],
    queryFn: () => api.masteryHistory(),
    staleTime: 60_000,
  });
}

export function useMistakes(opts = {}) {
  return useQuery({
    queryKey: ['mistakes', opts],
    queryFn: () => api.getMistakes(opts.topic, opts.resolved),
    staleTime: 30_000,
  });
}

export function useNotebook(topic) {
  return useQuery({
    queryKey: ['notebook', topic],
    queryFn: () => api.getNotebook(topic),
    staleTime: 30_000,
  });
}

export function useQuizHistory() {
  return useQuery({
    queryKey: ['quizHistory'],
    queryFn: () => api.getQuizHistory(),
    staleTime: 60_000,
  });
}

export function useFlashcardsDue() {
  return useQuery({
    queryKey: ['flashcardsDue'],
    queryFn: () => api.dueFlashcards(),
    staleTime: 30_000,
  });
}

export function useCertificates() {
  return useQuery({
    queryKey: ['certificates'],
    queryFn: () => api.getCertificates(),
    staleTime: 120_000,
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: () => api.getPreferences(),
    staleTime: 300_000,
  });
}

export function useResume() {
  return useQuery({
    queryKey: ['resume'],
    queryFn: () => api.getResume(),
    staleTime: 30_000,
  });
}

export function useMemory() {
  return useQuery({
    queryKey: ['memory'],
    queryFn: () => api.getMemory(),
    staleTime: 60_000,
  });
}

export function useProgressSnapshot() {
  return useQuery({
    queryKey: ['progressSnapshot'],
    queryFn: () => api.getProgressSnapshot(),
    staleTime: 60_000,
  });
}

// ── Mutations (POST/PUT/DELETE) ──

export function useSubmitAnswer(opts = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => api.submitAnswer(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['progress'] });
      qc.invalidateQueries({ queryKey: ['gamification'] });
      opts.onSuccess?.();
    },
  });
}

export function useSaveNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (note) => api.saveNote(note),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notebook'] }),
  });
}

export function useResolveMistake() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (mistakeId) => api.resolveMistake(mistakeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mistakes'] }),
  });
}

export function useCompleteQuest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (questId) => api.completeQuest(questId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quests'] });
      qc.invalidateQueries({ queryKey: ['gamification'] });
    },
  });
}

export function useChooseBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ subject, branchGroup, chosenNodeId }) =>
      api.chooseBranch(subject, branchGroup, chosenNodeId),
    onSuccess: (_, { subject }) =>
      qc.invalidateQueries({ queryKey: ['curriculum', subject] }),
  });
}
