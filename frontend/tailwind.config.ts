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
        bg: "#0B0F14",
        surface: "#111826",
        elevated: "#161F2E",
        border: "#1E2A3A",
        content: "#E6EAF2",
        muted: "#8A94A6",
        accent: {
          DEFAULT: "#8B5CF6",
          hover: "#7C3AED",
        },
        success: "#34D399",
        warn: "#FBBF24",
        danger: "#F87171",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.35), 0 12px 32px -20px rgba(0,0,0,0.9)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "fade-up": "fade-up 0.25s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
