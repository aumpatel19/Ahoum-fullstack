import type { Config } from "tailwindcss";

/**
 * One palette, defined once. Every colour in the UI comes from these tokens so
 * the theme stays coherent without anyone hand-picking hex values in a component.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#080B10",
        surface: "#0F1621",
        elevated: "#151E2C",
        border: "#1C2637",
        content: "#E9EDF5",
        muted: "#8792A6",
        accent: {
          DEFAULT: "#8B5CF6",
          hover: "#7C3AED",
          soft: "#A78BFA",
        },
        // A second hue, used sparingly for prices and "open" states, so the UI
        // is not one violet note repeated forty times.
        teal: "#2DD4BF",
        success: "#34D399",
        warn: "#FBBF24",
        danger: "#F87171",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
      },
      letterSpacing: {
        tighter: "-0.03em",
        looser: "0.08em",
      },
      boxShadow: {
        // Layered rather than one big blur: a tight contact shadow plus a wide
        // soft one is what makes a surface read as lifted instead of blurred.
        card: "0 1px 1px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.7)",
        lifted:
          "0 1px 1px rgba(0,0,0,0.4), 0 18px 40px -18px rgba(0,0,0,0.9), 0 0 0 1px rgba(139,92,246,0.25)",
        glow: "0 0 0 1px rgba(139,92,246,0.35), 0 12px 40px -12px rgba(139,92,246,0.35)",
      },
      backgroundImage: {
        "surface-sheen":
          "linear-gradient(180deg, rgba(255,255,255,0.045) 0%, rgba(255,255,255,0) 45%)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "fade-up": "fade-up 0.28s cubic-bezier(0.22, 1, 0.36, 1)",
      },
      transitionTimingFunction: {
        // Decelerating ease: motion that arrives rather than stops dead.
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
