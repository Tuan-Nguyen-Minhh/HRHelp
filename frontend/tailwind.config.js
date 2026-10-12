/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Space Grotesk"', "ui-sans-serif", "system-ui", "sans-serif"],
        ui: ['"Public Sans"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        doc: ["Literata", "Georgia", "serif"],
      },
      colors: {
        /* Tailwind default palette (slate/neutral/brand-cyan) is deprecated.
           Use linen/ink/son tokens below — see design-system/hr-help/MASTER.md */
        brand: {
          50: "#f0f9ff",
          100: "#e0f2fe",
          200: "#bae6fd",
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          800: "#075985",
          900: "#0c4a6e",
        },
        dark: {
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
        },
        linen: {
          DEFAULT: "#DCD8CC",
          2: "#E7E3D9",
          3: "#CFCABB",
        },
        paper: {
          DEFAULT: "#FBFAF7",
          2: "#F4F1EA",
          3: "#EFEBE1",
        },
        ink: {
          DEFAULT: "#332C22",
          2: "#5C554A",
          3: "#756F63",
          4: "#A29B8D",
        },
        rule: {
          DEFAULT: "#D8D1C3",
          2: "#B8AE9C",
        },
        son: {
          DEFAULT: "#8C2B2B",
          dark: "#722222",
          tint: "#F6EAE7",
          line: "#E2C4C0",
        },
        leather: {
          DEFAULT: "#4A3F30",
        },
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        "fade-in": "fadeIn 0.5s ease-out",
        "slide-up": "slideUp 0.5s ease-out",
        "slide-in-right": "slideInRight 0.3s ease-out",
        glow: "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideInRight: {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(14, 165, 233, 0.2)" },
          "100%": { boxShadow: "0 0 20px rgba(14, 165, 233, 0.4)" },
        },
      },
      boxShadow: {
        "brand-sm": "0 1px 3px rgba(14, 165, 233, 0.12)",
        "brand-md": "0 4px 14px rgba(14, 165, 233, 0.15)",
        "brand-lg": "0 8px 30px rgba(14, 165, 233, 0.2)",
        "brand-glow": "0 0 20px rgba(14, 165, 233, 0.3)",
        glass: "0 8px 32px rgba(0, 0, 0, 0.08)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
