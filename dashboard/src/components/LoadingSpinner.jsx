export default function LoadingSpinner({ label = 'Loading…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
      <div className="h-8 w-8 rounded-full border-4 border-gray-200 border-t-gold animate-spin" />
      <p className="mt-3 text-sm">{label}</p>
    </div>
  )
}
