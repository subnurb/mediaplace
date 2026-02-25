import React from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { setActiveTab, clearError } from '../store/jobSlice'
import FileUploadTab from '../components/FileUploadTab'
import UrlUploadTab from '../components/UrlUploadTab'
import JobStatus from '../components/JobStatus'

export default function Dashboard() {
  const dispatch = useDispatch()
  const { activeTab, error } = useSelector((s) => s.job)

  return (
    <div className="row justify-content-center mt-4">
      <div className="col-xl-8 col-lg-10">

        <JobStatus />

        {error && (
          <div className="alert alert-danger alert-dismissible" role="alert">
            <i className="bi bi-x-circle me-2"></i>{error}
            <button type="button" className="btn-close" onClick={() => dispatch(clearError())} />
          </div>
        )}

        <div className="card shadow-sm">
          <div className="card-header p-0 border-bottom-0">
            <ul className="nav nav-tabs card-header-tabs px-3 pt-2" role="tablist">
              <li className="nav-item">
                <button
                  className={`nav-link ${activeTab === 'file' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTab('file'))}
                  role="tab"
                >
                  <i className="bi bi-upload me-1"></i>Upload Files
                </button>
              </li>
              <li className="nav-item">
                <button
                  className={`nav-link ${activeTab === 'url' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTab('url'))}
                  role="tab"
                >
                  <i className="bi bi-link-45deg me-1"></i>From URL
                </button>
              </li>
            </ul>
          </div>
          <div className="card-body p-4">
            {activeTab === 'file' ? <FileUploadTab /> : <UrlUploadTab />}
          </div>
        </div>

      </div>
    </div>
  )
}
