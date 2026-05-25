export default function ErrorBanner({ message }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <strong className="font-semibold">Could not load data.</strong> {message}
    </div>
  )
}
