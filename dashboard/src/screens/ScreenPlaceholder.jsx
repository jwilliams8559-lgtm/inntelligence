export default function ScreenPlaceholder({ name }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-24">
      <div className="text-5xl mb-4" aria-hidden>🚧</div>
      <h1 className="text-2xl font-bold text-navy">{name}</h1>
      <p className="text-gray-500 mt-2">This screen is coming soon.</p>
    </div>
  )
}
