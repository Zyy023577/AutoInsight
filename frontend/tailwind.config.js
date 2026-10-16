/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07111f",
        panel: "#0e1b2e",
        cyan: "#55d8ff",
        lime: "#b4f37a",
      },
      boxShadow: {
        glow: "0 0 40px rgba(85, 216, 255, 0.12)",
      },
    },
  },
  plugins: [],
};
