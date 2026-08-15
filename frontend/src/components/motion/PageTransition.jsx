import { motion, useReducedMotion } from 'framer-motion';

/**
 * PageTransition — gentle 300ms cross-fade + rise when the route changes.
 * Respects prefers-reduced-motion.
 */
export default function PageTransition({ children }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={reduce ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="min-h-full"
    >
      {children}
    </motion.div>
  );
}