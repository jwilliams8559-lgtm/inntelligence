import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import UpgradeModal, { UPGRADE_MAILTO } from './UpgradeModal'

// Renders ONLY for founding_member plan. Gold normally; switches to orange
// inside 30 days, with an inline "Upgrade Now" CTA.
export default function FoundingMemberBanner() {
  const { user } = useAuth() || {}
  const [openUpgrade, setOpenUpgrade] = useState(false)
  if (!user) return null
  if ((user.plan_tier || '').toLowerCase() !== 'founding_member') return null
  if (!user.founding_member_end) return null

  const end = new Date(user.founding_member_end + 'T23:59:59')
  if (Number.isNaN(end.getTime())) return null
  const daysLeft = Math.max(0, Math.ceil((end.getTime() - Date.now()) / 86400000))
  const ending = daysLeft <= 30

  const endText = end.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })

  return (
    <>
      <div className={`w-full px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium shadow-sm ${
        ending ? 'bg-amber-500 text-navy' : 'bg-gold text-navy'
      }`}>
        <div className="min-w-0">
          {ending ? (
            <>
              <span className="font-bold">Your founding period ends in {daysLeft} day{daysLeft === 1 ? '' : 's'}.</span>{' '}
              <span className="hidden sm:inline">Upgrade to Professional to continue uninterrupted access.</span>
            </>
          ) : (
            <>
              <span className="font-bold">Founding Member</span>
              <span className="hidden sm:inline"> — Professional tier access free until {endText}</span>
              <span className="hidden sm:inline"> · {daysLeft} day{daysLeft === 1 ? '' : 's'} remaining</span>
            </>
          )}
        </div>
        {ending ? (
          <button onClick={() => setOpenUpgrade(true)}
            className="shrink-0 px-3 py-1.5 rounded-md bg-navy text-gold text-xs font-bold hover:bg-navy-light">
            Upgrade Now
          </button>
        ) : (
          <a href={UPGRADE_MAILTO}
            className="shrink-0 px-3 py-1.5 rounded-md bg-navy/10 hover:bg-navy/20 text-xs font-semibold">
            Learn more
          </a>
        )}
      </div>
      <UpgradeModal open={openUpgrade} feature="autopilot" onClose={() => setOpenUpgrade(false)} />
    </>
  )
}
