"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

// Simple re-export for one-off animations
export const MotionDiv = motion.div;

// FadeIn: opacity 0->1, translateY -10->0
interface FadeInProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}

export function FadeIn({ children, className, delay = 0, ...props }: FadeInProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

// SlideIn: configurable direction
interface SlideInProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
  direction?: "left" | "right" | "up" | "down";
  distance?: number;
  delay?: number;
}

export function SlideIn({
  children,
  className,
  direction = "left",
  distance = 20,
  delay = 0,
  ...props
}: SlideInProps) {
  const directionMap = {
    left: { x: -distance, y: 0 },
    right: { x: distance, y: 0 },
    up: { x: 0, y: -distance },
    down: { x: 0, y: distance },
  };

  const offset = directionMap[direction];

  return (
    <motion.div
      initial={{ opacity: 0, ...offset }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration: 0.3, delay }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

// StaggerContainer: staggers children with delay
interface StaggerContainerProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
  staggerDelay?: number;
}

export function StaggerContainer({
  children,
  className,
  staggerDelay = 0.1,
  ...props
}: StaggerContainerProps) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: staggerDelay,
          },
        },
      }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

// MotionCard: hover scale + shadow, tap scale
interface MotionCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
}

export const MotionCard = forwardRef<HTMLDivElement, MotionCardProps>(
  function MotionCard({ children, className, ...props }, ref) {
    return (
      <motion.div
        ref={ref}
        variants={{
          hidden: { opacity: 0, y: -10 },
          visible: { opacity: 1, y: 0 },
        }}
        whileHover={{ scale: 1.02, boxShadow: "0 8px 30px rgba(0,0,0,0.12)" }}
        whileTap={{ scale: 0.98 }}
        transition={{ duration: 0.3 }}
        className={cn("cursor-pointer", className)}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);

// PageTransition: fade-in + slide-up for page content
interface PageTransitionProps {
  children: React.ReactNode;
  className?: string;
}

export function PageTransition({ children, className }: PageTransitionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
