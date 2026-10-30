import "./globals.css";

export const metadata = {
  title: "CareCompass — a space to check in",
  description: "A private, non-diagnostic space to reflect on wellbeing over time.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
