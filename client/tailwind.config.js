/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#030305", // tło
          900: "#0a0a10", // kafelki
          800: "#12121b", // kafelki podniesione / inputy
          700: "#1c1c28",
          600: "#2a2a3a",
        },
        neon: {
          violet: "#a855f7",
          green: "#22e58a",
          blue: "#38bdf8",
        },
        profit: "#34d399",
        loss: "#f87171",
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      boxShadow: {
        "neon-violet": "0 0 24px -6px rgba(168, 85, 247, 0.55)",
        "neon-green": "0 0 24px -6px rgba(34, 229, 138, 0.5)",
        "neon-blue": "0 0 24px -6px rgba(56, 189, 248, 0.55)",
      },
      keyframes: {
        "fade-in": { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "none" } },
        "pop-in": { from: { opacity: 0, transform: "scale(0.97)" }, to: { opacity: 1, transform: "none" } },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "pop-in": "pop-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
};
