import { useState, useEffect } from 'react'
import { usePrices } from '../context/PriceContext'
import {
  getGiftShop, addGiftCategory, deleteGiftCategory,
  addGiftItem, updateGiftItem, deleteGiftItem,
} from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, LastUpdated, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const FULFILLMENT_TONE = {
  'in-stock': 'emerald', dropship: 'navy', consignment: 'gold', 'print-on-demand': 'gray',
}
const blankItem = (cid) => ({
  category_id: cid, name: '', description: '', price: '', cost: '',
  fulfillment: 'in-stock', inventory: '', reorder_point: '', supplier: '',
  units_sold_month: '', units_sold_last_month: '',
})

export default function GiftShop() {
  const { lastUpdated } = usePrices()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [editor, setEditor] = useState(null)   // {mode, item}
  const [newCat, setNewCat] = useState('')

  const load = () => getGiftShop().then(setData).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading gift shop…" />

  const s = data.summary
  const marginPct = s.total_monthly_revenue ? Math.round(s.total_monthly_margin / s.total_monthly_revenue * 100) : 0

  const saveItem = async (form) => {
    try {
      if (editor.mode === 'edit') await updateGiftItem(editor.item.id, form)
      else await addGiftItem(form)
      setEditor(null); await load()
    } catch (e) { setErr(e.message) }
  }
  const removeItem = async (iid) => { await deleteGiftItem(iid); await load() }
  const addCategory = async () => { if (newCat) { await addGiftCategory({ name: newCat }); setNewCat(''); await load() } }
  const removeCategory = async (cid) => { await deleteGiftCategory(cid); await load() }

  return (
    <div>
      <ScreenHeader
        title="Gift Shop"
        subtitle="Retail catalog, inventory, and sales — full category & item management"
        right={<LastUpdated at={lastUpdated} />}
      />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        <StatCard label="Monthly Revenue" value={usd(s.total_monthly_revenue)} sub={`${usd(s.total_monthly_revenue * 12)}/yr`} accent />
        <StatCard label="Gross Margin" value={usd(s.total_monthly_margin)} sub={`${marginPct}% blended`} />
        <StatCard label="Units / Month" value={s.total_units} sub="sold" />
        <StatCard label="Categories" value={s.category_count} sub="product lines" />
        <StatCard label="SKUs" value={s.item_count} sub="items" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card title="🏆 Best Sellers">
          <div className="space-y-1">
            {data.best_sellers.map((i, n) => (
              <div key={i.id} className="flex justify-between text-sm border-b border-gray-100 py-1.5">
                <span className="text-navy"><span className="text-gold font-bold mr-1">{n + 1}.</span>{i.name}</span>
                <span className="font-semibold text-emerald-700">{usd(i.revenue_month)}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="🐌 Slow Movers (0 sales / 30d)">
          {data.slow_movers.length === 0 ? <p className="text-sm text-gray-400">None — everything is moving.</p> : (
            <div className="space-y-1">
              {data.slow_movers.map((i) => (
                <div key={i.id} className="flex justify-between text-sm border-b border-gray-100 py-1.5">
                  <span className="text-navy">{i.name}</span>
                  <span className="text-gray-400">{i.inventory} in stock</span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="⚠️ Low Stock (reorder)">
          {data.low_stock.length === 0 ? <p className="text-sm text-gray-400">All above reorder points.</p> : (
            <div className="space-y-1">
              {data.low_stock.map((i) => (
                <div key={i.id} className="flex justify-between text-sm border-b border-gray-100 py-1.5">
                  <span className="text-navy">{i.name}</span>
                  <span className="text-rose-600 font-semibold">{i.inventory} ≤ {i.reorder_point}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <input value={newCat} onChange={(e) => setNewCat(e.target.value)} placeholder="New category name…"
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
        <button onClick={addCategory} className="px-3 py-1.5 bg-navy text-white text-sm font-semibold rounded-lg hover:bg-navy-light">+ Add Category</button>
      </div>

      <div className="space-y-4">
        {data.categories.map((cat) => (
          <Card key={cat.id} title={`${cat.emoji} ${cat.name}`} right={
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-gray-400">{usd(cat.revenue_month)}/mo · {cat.item_count} SKUs</span>
              <button onClick={() => setEditor({ mode: 'add', item: blankItem(cat.id) })} className="text-xs font-semibold text-navy hover:text-gold">+ Item</button>
              <button onClick={() => removeCategory(cat.id)} className="text-xs text-rose-500 hover:text-rose-700">Delete</button>
            </div>
          }>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
                  <tr>
                    <th className="text-left py-1">Item</th>
                    <th className="text-right">Price</th>
                    <th className="text-right">Cost</th>
                    <th className="text-right">Margin</th>
                    <th className="text-left pl-3">Fulfillment</th>
                    <th className="text-right">Inv</th>
                    <th className="text-right">Sold</th>
                    <th className="text-right">Trend</th>
                    <th className="text-right">Rev</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {cat.items.map((it) => (
                    <tr key={it.id} className={`border-t border-gray-100 ${it.low_stock ? 'bg-rose-50' : ''}`}>
                      <td className="py-1.5"><span className="font-medium text-navy">{it.name}</span><div className="text-[10px] text-gray-400">{it.supplier}</div></td>
                      <td className="text-right text-gray-700">{usd(it.price)}</td>
                      <td className="text-right text-gray-500">{usd(it.cost)}</td>
                      <td className="text-right font-semibold text-navy">{it.margin_pct}%</td>
                      <td className="pl-3"><Pill tone={FULFILLMENT_TONE[it.fulfillment] || 'gray'}>{it.fulfillment}</Pill></td>
                      <td className={`text-right ${it.low_stock ? 'text-rose-600 font-bold' : 'text-gray-600'}`}>{it.inventory}</td>
                      <td className="text-right text-gray-600">{it.units_sold_month}</td>
                      <td className={`text-right font-semibold ${it.trend_pct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{it.trend_pct >= 0 ? '+' : ''}{it.trend_pct}%</td>
                      <td className="text-right text-gray-700">{usd(it.revenue_month)}</td>
                      <td className="text-right whitespace-nowrap">
                        <button onClick={() => setEditor({ mode: 'edit', item: it })} className="text-navy hover:text-gold mr-2">Edit</button>
                        <button onClick={() => removeItem(it.id)} className="text-rose-400 hover:text-rose-600">✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))}
      </div>

      {editor && (
        <ItemEditor
          editor={editor} fulfillmentTypes={data.fulfillment_types}
          onClose={() => setEditor(null)} onSave={saveItem}
        />
      )}
    </div>
  )
}

const FIELD_CLS = 'w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gold'
const Field = ({ label, value, onChange, type = 'text' }) => (
  <div>
    <label className="block text-[11px] font-semibold text-gray-500 mb-0.5">{label}</label>
    <input type={type} value={value ?? ''} onChange={onChange} className={FIELD_CLS} />
  </div>
)

function ItemEditor({ editor, fulfillmentTypes, onClose, onSave }) {
  const [form, setForm] = useState({ ...editor.item })
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="bg-navy text-white px-5 py-4 flex items-center justify-between sticky top-0">
          <div className="font-bold">{editor.mode === 'edit' ? 'Edit Item' : 'Add Item'}</div>
          <button onClick={onClose} className="text-white/70 hover:text-white text-xl leading-none">✕</button>
        </div>
        <div className="p-5 space-y-3">
          <Field label="Name" value={form.name} onChange={set('name')} />
          <div>
            <label className="block text-[11px] font-semibold text-gray-500 mb-0.5">Description</label>
            <textarea value={form.description ?? ''} onChange={set('description')} rows={2} className={FIELD_CLS} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Price ($)" value={form.price} onChange={set('price')} type="number" />
            <Field label="Cost ($)" value={form.cost} onChange={set('cost')} type="number" />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-gray-500 mb-0.5">Fulfillment</label>
            <select value={form.fulfillment} onChange={set('fulfillment')} className={FIELD_CLS}>
              {fulfillmentTypes.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Inventory" value={form.inventory} onChange={set('inventory')} type="number" />
            <Field label="Reorder Point" value={form.reorder_point} onChange={set('reorder_point')} type="number" />
          </div>
          <Field label="Supplier" value={form.supplier} onChange={set('supplier')} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Units Sold (mo)" value={form.units_sold_month} onChange={set('units_sold_month')} type="number" />
            <Field label="Units Sold (last mo)" value={form.units_sold_last_month} onChange={set('units_sold_last_month')} type="number" />
          </div>
          <button onClick={() => onSave(form)} className="w-full bg-gold text-navy font-semibold py-2.5 rounded-lg hover:bg-gold-light transition-colors">
            {editor.mode === 'edit' ? 'Save Changes' : 'Add Item'}
          </button>
        </div>
      </div>
    </div>
  )
}
