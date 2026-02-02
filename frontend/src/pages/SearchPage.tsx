import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Search, Sparkles, Loader2, Check, AlertCircle, Clock } from 'lucide-react'
import { searchLeads, previewSearch, type SearchPreview } from '../services/api'
import { useNavigate } from 'react-router-dom'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [maxResults, setMaxResults] = useState(50)
  const [preview, setPreview] = useState<SearchPreview | null>(null)
  const [searchStatus, setSearchStatus] = useState('')
  const navigate = useNavigate()

  const previewMutation = useMutation({
    mutationFn: () => previewSearch(query),
    onSuccess: (data) => setPreview(data),
  })

  const searchMutation = useMutation({
    mutationFn: () => {
      setSearchStatus('Connecting to Apify...')
      return searchLeads(query, maxResults)
    },
    onSuccess: (data) => {
      setSearchStatus('')
      navigate(`/leads?campaign_id=${data.campaign_id}`)
    },
    onError: () => {
      setSearchStatus('')
    }
  })

  const handlePreview = () => {
    if (query.length >= 5) {
      previewMutation.mutate()
    }
  }

  const handleSearch = () => {
    if (query.length >= 5) {
      setSearchStatus('Parsing query with AI...')
      setTimeout(() => {
        if (searchMutation.isPending) {
          setSearchStatus('Fetching leads from Apify (this may take 1-2 minutes)...')
        }
      }, 3000)
      searchMutation.mutate()
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Search Leads</h1>
        <p className="text-gray-500 mt-1">
          Describe your ideal leads in natural language
        </p>
      </div>

      {/* Search Form */}
      <div className="card space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Search Query
          </label>
          <textarea
            className="input min-h-[100px]"
            placeholder="Example: CEOs and CTOs at tech companies in Spain with 50-200 employees"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={searchMutation.isPending}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Maximum Results
          </label>
          <input
            type="number"
            className="input w-32"
            value={maxResults}
            onChange={(e) => setMaxResults(Math.min(500, Math.max(1, Number(e.target.value))))}
            min={1}
            max={500}
            disabled={searchMutation.isPending}
          />
        </div>

        <div className="flex gap-3">
          <button
            className="btn btn-secondary flex items-center"
            onClick={handlePreview}
            disabled={query.length < 5 || previewMutation.isPending || searchMutation.isPending}
          >
            {previewMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4 mr-2" />
            )}
            Preview Filters
          </button>
          <button
            className="btn btn-primary flex items-center"
            onClick={handleSearch}
            disabled={query.length < 5 || searchMutation.isPending}
          >
            {searchMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Search className="w-4 h-4 mr-2" />
            )}
            Search Leads
          </button>
        </div>
      </div>

      {/* Loading State */}
      {searchMutation.isPending && (
        <div className="card bg-blue-50 border-blue-200">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 border-4 border-blue-200 rounded-full"></div>
              <div className="absolute top-0 left-0 w-12 h-12 border-4 border-blue-600 rounded-full animate-spin border-t-transparent"></div>
            </div>
            <div>
              <h3 className="font-semibold text-blue-900">Searching for leads...</h3>
              <p className="text-blue-700 text-sm flex items-center mt-1">
                <Clock className="w-4 h-4 mr-1" />
                {searchStatus || 'Processing...'}
              </p>
              <div className="w-64 bg-blue-200 rounded-full h-2 mt-2">
                <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preview Results */}
      {preview && !searchMutation.isPending && (
        <div className="card">
          <div className="flex items-start gap-3 mb-4">
            <div className={`p-2 rounded-lg ${preview.confidence > 0.7 ? 'bg-green-100' : 'bg-yellow-100'}`}>
              {preview.confidence > 0.7 ? (
                <Check className="w-5 h-5 text-green-600" />
              ) : (
                <AlertCircle className="w-5 h-5 text-yellow-600" />
              )}
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">AI Interpretation</h3>
              <p className="text-gray-600 mt-1">{preview.interpretation}</p>
              <p className="text-sm text-gray-500 mt-1">
                Confidence: {Math.round(preview.confidence * 100)}%
              </p>
            </div>
          </div>

          <div className="border-t pt-4">
            <h4 className="font-medium text-gray-900 mb-3">Filters to be applied:</h4>
            <div className="grid grid-cols-2 gap-3">
              {preview.filters.contact_job_title && (
                <FilterTag label="Job Titles" values={preview.filters.contact_job_title} />
              )}
              {preview.filters.contact_seniority && (
                <FilterTag label="Seniority" values={preview.filters.contact_seniority} />
              )}
              {preview.filters.contact_location && (
                <FilterTag label="Location" values={preview.filters.contact_location} />
              )}
              {preview.filters.company_industry && (
                <FilterTag label="Industries" values={preview.filters.company_industry} />
              )}
              {preview.filters.company_size && (
                <FilterTag label="Company Size" values={preview.filters.company_size} />
              )}
              {preview.filters.company_location && (
                <FilterTag label="Company Location" values={preview.filters.company_location} />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {searchMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          <AlertCircle className="w-5 h-5 inline mr-2" />
          Error: {(searchMutation.error as Error).message}
        </div>
      )}

      {/* Examples */}
      {!searchMutation.isPending && (
        <div className="card bg-gray-50">
          <h3 className="font-semibold text-gray-900 mb-3">Example Queries</h3>
          <ul className="space-y-2 text-gray-600">
            <li
              className="cursor-pointer hover:text-blue-600"
              onClick={() => setQuery('CEOs and founders at SaaS companies in United States with 50-200 employees')}
            >
              "CEOs and founders at SaaS companies in United States with 50-200 employees"
            </li>
            <li
              className="cursor-pointer hover:text-blue-600"
              onClick={() => setQuery('Marketing directors at e-commerce companies in Europe')}
            >
              "Marketing directors at e-commerce companies in Europe"
            </li>
            <li
              className="cursor-pointer hover:text-blue-600"
              onClick={() => setQuery('CTOs and VPs of Engineering at AI startups')}
            >
              "CTOs and VPs of Engineering at AI startups"
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}

function FilterTag({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="bg-gray-100 rounded-lg p-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm font-medium text-gray-900 mt-1">{values.join(', ')}</p>
    </div>
  )
}
