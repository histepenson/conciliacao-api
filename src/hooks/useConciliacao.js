import { useState } from 'react'
import { processarConciliação } from '../api/conciliacaoApi'
import { validateFile } from '../utils/fileValidation'

export function useConciliacao() {

  const [files, setFiles] = useState({ origem: null, contabil: null, geral: null })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const setFile = (type, file) => {
    const error = validateFile(file)
    if (error) return setError(error)
    setFiles(prev => ({ ...prev, [type]: file }))
  }

  const removeFile = (type) => {
    setFiles(prev => ({ ...prev, [type]: null }))
  }

  const reset = () => {
    setFiles({ origem: null, contabil: null, geral: null })
    setResult(null)
    setError(null)
  }

  const processFiles = async () => {
    setLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('arquivo_origem', files.origem)
      formData.append('arquivo_contabil', files.contabil)
      formData.append('arquivo_geral_contabilidade', files.geral)

      const response = await processarConciliação(formData)
      setResult(response.data)

    } catch (err) {
      setError(err.response?.data?.detail ?? 'Erro ao processar.')
    }

    setLoading(false)
  }

  return { files, setFile, removeFile, result, processFiles, reset, loading, error }
}
