import { motion, useReducedMotion } from 'framer-motion';

/**
 * Reveal — premium scroll entrance (fade + gentle rise).
 * Respects prefers-reduced-motion: renders without animation.
 * Props:
 *   delay (s), y (px), once (bool), as (element), className
 */
export default function Reveal({ children, delay = 0, y = 18, once = true, className, ...rest }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once, margin: '-60px' }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}