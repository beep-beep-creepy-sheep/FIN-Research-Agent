import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        paper: "#f7f8f5",
        line: "#d8ddd2",
        accent: "#0f766e",
        risk: "#b42318"
      }
    },
  },
  plugins: [],
};

export default config;

