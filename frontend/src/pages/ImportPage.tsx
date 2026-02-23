import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, ArrowRight, ArrowLeft, X } from 'lucide-react'
import Papa from 'papaparse'
import { previewCSVImport, executeCSVImport, type CSVPreviewResponse, type CSVImportResponse } from '../services/api'

type Step = 'upload' | 'preview' | 'result'

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  invitation_sent: 'Invitation Sent',
  connected: 'Connected',
  in_conversation: 'In Conversation',
}

export default function ImportPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('upload')
  const [, setFile] = useState<File | null>(null)
  const [parsedRows, setParsedRows] = useState<Record<string, unknown>[]>([])
  const [preview, setPreview] = useState<CSVPreviewResponse | null>(null)
  const [result, setResult] = useState<CSVImportResponse | null>(null)
  const [campaignName, setCampaignName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)

  const handleFile = useCallback(async (selectedFile: File) => {
    setFile(selectedFile)
    setError(null)
    setIsLoading(true)

    try {
      // Parse CSV client-side
      Papa.parse(selectedFile, {
        header: true,
        skipEmptyLines: true,
        complete: async (results) => {
          setParsedRows(results.data as Record<string, unknown>[])
          setCampaignName(`CSV Import - ${new Date().toLocaleDateString()}`)

          // Get server preview (duplicate detection)
          try {
            const previewData = await previewCSVImport(selectedFile)
            setPreview(previewData)
            setStep('preview')
          } catch (err: unknown) {
            const errorMsg = err instanceof Error ? err.message : 'Failed to preview CSV'
            setError(errorMsg)
          } finally {
            setIsLoading(false)
          }
        },
        error: (err) => {
          setError(`CSV parse error: ${err.message}`)
          setIsLoading(false)
        }
      })
    } catch {
      setError('Failed to read file')
      setIsLoading(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile?.name.endsWith('.csv')) {
      handleFile(droppedFile)
    } else {
      setError('Please drop a CSV file')
    }
  }, [handleFile])

  const handleExecuteImport = async () => {
    if (!preview || !parsedRows.length || !campaignName) return

    setIsLoading(true)
    setError(null)

    try {
      const importResult = await executeCSVImport({
        campaign_name: campaignName,
        rows: parsedRows,
        column_mapping: preview.column_mapping,
      })
      setResult(importResult)
      setStep('result')
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Import failed'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Import Leads from CSV</h1>
        <p className="text-gray-500 mt-1">Upload a CSV file to import leads into a new campaign</p>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center gap-4">
        {(['upload', 'preview', 'result'] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step === s ? 'bg-blue-600 text-white' :
              (['upload', 'preview', 'result'].indexOf(step) > i) ? 'bg-green-500 text-white' :
              'bg-gray-200 text-gray-500'
            }`}>
              {(['upload', 'preview', 'result'].indexOf(step) > i) ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                i + 1
              )}
            </div>
            <span className={`text-sm font-medium ${step === s ? 'text-gray-900' : 'text-gray-500'}`}>
              {s === 'upload' ? 'Upload' : s === 'preview' ? 'Preview' : 'Result'}
            </span>
            {i < 2 && <ArrowRight className="w-4 h-4 text-gray-300 ml-2" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <p className="text-red-700">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Step 1: Upload */}
      {step === 'upload' && (
        <div
          className={`card border-2 border-dashed transition-colors ${
            dragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300'
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center justify-center py-12">
            {isLoading ? (
              <>
                <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
                <p className="text-gray-600">Processing CSV file...</p>
              </>
            ) : (
              <>
                <Upload className="w-12 h-12 text-gray-400 mb-4" />
                <p className="text-lg font-medium text-gray-900 mb-2">
                  Drag & drop your CSV file here
                </p>
                <p className="text-gray-500 mb-4">or click to browse</p>
                <label className="btn btn-primary cursor-pointer">
                  <FileText className="w-4 h-4 mr-2" />
                  Choose CSV File
                  <input
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) handleFile(f)
                    }}
                  />
                </label>
              </>
            )}
          </div>
        </div>
      )}

      {/* Step 2: Preview */}
      {step === 'preview' && preview && (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card">
              <p className="text-sm text-gray-500">Total Rows</p>
              <p className="text-2xl font-semibold">{preview.total_rows}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">New Leads</p>
              <p className="text-2xl font-semibold text-green-600">{preview.new_count}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Duplicates (skip)</p>
              <p className="text-2xl font-semibold text-orange-600">{preview.duplicate_count}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Columns Mapped</p>
              <p className="text-2xl font-semibold text-blue-600">
                {Object.keys(preview.column_mapping).length}
              </p>
            </div>
          </div>

          {/* Status breakdown */}
          {Object.keys(preview.status_breakdown).length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-3">Status Detection</h3>
              <div className="flex flex-wrap gap-3">
                {Object.entries(preview.status_breakdown).map(([status, count]) => (
                  <span key={status} className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700">
                    {STATUS_LABELS[status] || status}: <span className="font-semibold ml-1">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Preview table */}
          <div className="card overflow-hidden p-0">
            <div className="px-6 py-4 border-b">
              <h3 className="font-semibold text-gray-900">Preview (first 5 rows)</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Job Title</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Country</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {preview.preview_rows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium">{String(row.first_name || '')} {String(row.last_name || '')}</td>
                      <td className="px-4 py-2 text-gray-600">{String(row.job_title || row.headline || '')}</td>
                      <td className="px-4 py-2 text-gray-600">{String(row.company_name || '')}</td>
                      <td className="px-4 py-2 text-gray-600 font-mono text-xs">{String(row.email || '')}</td>
                      <td className="px-4 py-2 text-gray-600">{String(row.country || '')}</td>
                      <td className="px-4 py-2">
                        <span className="px-2 py-0.5 rounded text-xs bg-gray-100">
                          {STATUS_LABELS[String(row.status || 'new')] || String(row.status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Campaign name + import button */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-3">Campaign Details</h3>
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Campaign Name</label>
                <input
                  type="text"
                  className="input w-full"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                  placeholder="Enter campaign name..."
                />
              </div>
              <div className="flex gap-2">
                <button
                  className="btn btn-secondary flex items-center"
                  onClick={() => { setStep('upload'); setFile(null); setPreview(null) }}
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </button>
                <button
                  className="btn btn-primary flex items-center"
                  onClick={handleExecuteImport}
                  disabled={isLoading || !campaignName || preview.new_count === 0}
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Upload className="w-4 h-4 mr-2" />
                  )}
                  Import {preview.new_count} Leads
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Result */}
      {step === 'result' && result && (
        <div className="space-y-6">
          <div className="card bg-green-50 border-green-200">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-green-900">Import Successful!</h3>
                <p className="text-green-700">
                  {result.imported} leads imported into "{result.campaign_name}"
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card">
              <p className="text-sm text-gray-500">Total Processed</p>
              <p className="text-2xl font-semibold">{result.total_processed}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Imported</p>
              <p className="text-2xl font-semibold text-green-600">{result.imported}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Duplicates Skipped</p>
              <p className="text-2xl font-semibold text-orange-600">{result.duplicates_skipped}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Errors</p>
              <p className="text-2xl font-semibold text-red-600">{result.errors}</p>
            </div>
          </div>

          {Object.keys(result.status_breakdown).length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-3">Imported by Status</h3>
              <div className="flex flex-wrap gap-3">
                {Object.entries(result.status_breakdown).map(([status, count]) => (
                  <span key={status} className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100">
                    {STATUS_LABELS[status] || status}: <span className="font-semibold ml-1">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              className="btn btn-primary"
              onClick={() => navigate(`/leads?campaign_id=${result.campaign_id}`)}
            >
              View Imported Leads
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => { setStep('upload'); setFile(null); setPreview(null); setResult(null) }}
            >
              Import Another CSV
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
