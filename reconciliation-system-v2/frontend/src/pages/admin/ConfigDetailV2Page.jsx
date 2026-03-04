import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { 
  ArrowLeftIcon,
  ArrowPathIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
  ArrowDownIcon,
  ArrowRightIcon,
  DocumentTextIcon,
  ServerIcon,
  CloudArrowUpIcon,
  CircleStackIcon
} from '@heroicons/react/24/outline'
import { 
  configsApiV2, 
  dataSourcesApiV2, 
  workflowsApiV2, 
  outputsApiV2 
} from '../../services/api'

export default function ConfigDetailV2Page() {
  const { id } = useParams()
  const navigate = useNavigate()
  
  const [config, setConfig] = useState(null)
  const [dataSources, setDataSources] = useState([])
  const [workflowSteps, setWorkflowSteps] = useState([])
  const [outputConfigs, setOutputConfigs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    loadData()
  }, [id])

  const loadData = async () => {
    try {
      setLoading(true)
      
      // Load all data in parallel
      const [configRes, sourcesRes, workflowsRes, outputsRes] = await Promise.all([
        configsApiV2.get(id),
        dataSourcesApiV2.getByConfig(id),
        workflowsApiV2.getByConfig(id),
        outputsApiV2.getByConfig(id)
      ])
      
      setConfig(configRes.data)
      setDataSources(sourcesRes.data)
      setWorkflowSteps(workflowsRes.data.sort((a, b) => a.step_order - b.step_order))
      setOutputConfigs(outputsRes.data.sort((a, b) => a.display_order - b.display_order))
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu')
    } finally {
      setLoading(false)
    }
  }

  const getSourceTypeIcon = (type) => {
    switch (type) {
      case 'FILE_UPLOAD': return CloudArrowUpIcon
      case 'DATABASE': return CircleStackIcon
      case 'SFTP': return ServerIcon
      case 'API': return DocumentTextIcon
      default: return DocumentTextIcon
    }
  }

  const getSourceTypeColor = (type) => {
    switch (type) {
      case 'FILE_UPLOAD': return 'bg-blue-100 text-blue-800 border-blue-300'
      case 'DATABASE': return 'bg-green-100 text-green-800 border-green-300'
      case 'SFTP': return 'bg-purple-100 text-purple-800 border-purple-300'
      case 'API': return 'bg-orange-100 text-orange-800 border-orange-300'
      default: return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!config) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Không tìm thấy cấu hình</p>
        <Link to="/admin/configs-v2" className="text-blue-600 hover:underline mt-2 inline-block">
          ← Quay lại danh sách
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <Link 
            to="/admin/configs-v2" 
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ArrowLeftIcon className="h-4 w-4 mr-1" />
            Quay lại danh sách
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">
            {config.partner_code}/{config.service_code}
          </h1>
          <p className="text-gray-500">{config.partner_name} - {config.service_name}</p>
        </div>
        <Link
          to={`/admin/configs-v2/${id}/edit`}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-md font-medium transition-colors"
        >
          <PencilIcon className="h-5 w-5 mr-2" />
          Chỉnh sửa
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">{error}</div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {['overview', 'data-sources', 'workflow', 'report'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab === 'overview' && 'Tổng quan'}
              {tab === 'data-sources' && `Nguồn dữ liệu (${dataSources.length})`}
              {tab === 'workflow' && `Workflow (${workflowSteps.length} bước)`}
              {tab === 'report' && '📊 Report Template'}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Basic Info */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Thông tin cơ bản</h3>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-gray-500">Partner Code:</dt>
                <dd className="font-medium">{config.partner_code}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Service Code:</dt>
                <dd className="font-medium">{config.service_code}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Trạng thái:</dt>
                <dd>
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    config.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {config.is_active ? 'Active' : 'Inactive'}
                  </span>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Hiệu lực từ:</dt>
                <dd className="font-medium">{config.valid_from}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Hiệu lực đến:</dt>
                <dd className="font-medium">{config.valid_to || 'Không giới hạn'}</dd>
              </div>
            </dl>
          </div>

          {/* Summary Stats */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Thống kê cấu hình</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <div className="text-3xl font-bold text-blue-600">{dataSources.length}</div>
                <div className="text-sm text-gray-500">Nguồn dữ liệu</div>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <div className="text-3xl font-bold text-purple-600">{workflowSteps.length}</div>
                <div className="text-sm text-gray-500">Workflow Steps</div>
              </div>
            </div>
            
            {/* Report Template status */}
            <div className="mt-4 p-3 rounded-lg border">
              <div className="flex items-center">
                <span className="text-sm text-gray-500 mr-2">Report Template:</span>
                {config.report_template_path ? (
                  <span className="text-sm text-green-600 font-medium">✓ Đã cấu hình</span>
                ) : (
                  <span className="text-sm text-gray-400">Chưa cấu hình</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'data-sources' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 shadow-md font-medium transition-colors">
              <PlusIcon className="h-4 w-4 mr-1" />
              Thêm nguồn
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dataSources.map((ds) => {
              const IconComponent = getSourceTypeIcon(ds.source_type)
              return (
                <div key={ds.id} className={`border rounded-lg p-4 ${getSourceTypeColor(ds.source_type)}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center">
                      <IconComponent className="h-5 w-5 mr-2" />
                      <span className="font-bold text-lg">{ds.source_name}</span>
                    </div>
                    <span className="text-xs px-2 py-0.5 bg-white/50 rounded">
                      {ds.source_type}
                    </span>
                  </div>
                  <p className="text-sm">{ds.display_name}</p>
                  {ds.is_required && (
                    <span className="inline-block mt-2 text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded">
                      Bắt buộc
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {activeTab === 'workflow' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 shadow-md font-medium transition-colors">
              <PlusIcon className="h-4 w-4 mr-1" />
              Thêm bước
            </button>
          </div>

          {/* Workflow visualization */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="space-y-4">
              {workflowSteps.map((step, index) => (
                <div key={step.id} className="relative">
                  {index > 0 && (
                    <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                      <ArrowDownIcon className="h-6 w-6 text-gray-400" />
                    </div>
                  )}
                  <div className={`border-2 rounded-lg p-4 ${
                    step.is_final_output ? 'border-green-500 bg-green-50' : 'border-gray-300'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white font-bold">
                          {step.step_order}
                        </span>
                        <div>
                          <h4 className="font-medium">{step.step_name}</h4>
                          <div className="flex items-center text-sm text-gray-500 mt-1">
                            <span className="font-mono bg-blue-100 px-2 py-0.5 rounded">{step.left_source}</span>
                            <ArrowRightIcon className="h-4 w-4 mx-2" />
                            <span className="font-mono bg-purple-100 px-2 py-0.5 rounded">{step.right_source}</span>
                            <span className="mx-2">=</span>
                            <span className="font-mono bg-green-100 px-2 py-0.5 rounded">{step.output_name}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                          {step.join_type} join
                        </span>
                        {step.is_final_output && (
                          <span className="text-xs bg-green-500 text-white px-2 py-1 rounded">
                            Final Output
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Matching Rules Preview */}
                    <div className="mt-3 text-sm text-gray-600">
                      <strong>Matching:</strong> {step.matching_rules?.match_type || 'expression'}
                      {step.matching_rules?.rules && (
                        <span className="ml-2">
                          ({step.matching_rules.rules.length} rules)
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'report' && (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-6">
            <h3 className="text-lg font-medium mb-4">📊 Report Template</h3>
            
            {config.report_template_path ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center">
                    <DocumentTextIcon className="h-8 w-8 text-green-600 mr-3" />
                    <div>
                      <p className="font-medium">{config.report_template_path}</p>
                      <p className="text-sm text-gray-500">Template file</p>
                    </div>
                  </div>
                </div>
                
                {config.report_cell_mapping && (
                  <div>
                    <h4 className="font-medium mb-2">Cell Mapping</h4>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <pre className="text-sm overflow-x-auto">
                        {JSON.stringify(config.report_cell_mapping, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <DocumentTextIcon className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p>Chưa cấu hình Report Template</p>
                <p className="text-sm mt-2">Vào trang Chỉnh sửa để cấu hình template báo cáo.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
