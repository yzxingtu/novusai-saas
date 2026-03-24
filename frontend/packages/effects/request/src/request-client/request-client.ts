import type { AxiosInstance, AxiosResponse } from 'axios';

import type { RequestClientConfig, RequestClientOptions } from './types';

import { bindMethods, isString, merge } from '@vben/utils';

import axios from 'axios';
import qs from 'qs';

import { FileDownloader } from './modules/downloader';
import { InterceptorManager } from './modules/interceptor';
import { SSE } from './modules/sse';
import { FileUploader } from './modules/uploader';

function getParamsSerializer(
  paramsSerializer: RequestClientOptions['paramsSerializer'],
) {
  if (isString(paramsSerializer)) {
    switch (paramsSerializer) {
      case 'brackets': {
        return (params: any) =>
          qs.stringify(params, { arrayFormat: 'brackets' });
      }
      case 'comma': {
        return (params: any) => qs.stringify(params, { arrayFormat: 'comma' });
      }
      case 'indices': {
        return (params: any) =>
          qs.stringify(params, { arrayFormat: 'indices' });
      }
      case 'repeat': {
        return (params: any) => qs.stringify(params, { arrayFormat: 'repeat' });
      }
    }
  }
  return paramsSerializer;
}

class RequestClient {
  public addRequestInterceptor: InterceptorManager['addRequestInterceptor'];

  public addResponseInterceptor: InterceptorManager['addResponseInterceptor'];
  public download: FileDownloader['download'];

  public readonly instance: AxiosInstance;
  // 是否正在刷新 token / Refresh-in-flight flag
  public isRefreshing = false;
  public postSSE: SSE['postSSE'];
  // 刷新 token 队列 / Queued callbacks after refresh
  public refreshTokenQueue: ((token: string) => void)[] = [];
  public requestSSE: SSE['requestSSE'];
  public upload: FileUploader['upload'];

  /**
   * 构造函数，用于创建 Axios 实例 / Construct axios-backed client
   * @param options Axios 请求配置（可选）/ optional axios config
   */
  constructor(options: RequestClientOptions = {}) {
    // 合并默认配置和传入的配置 / Merge defaults with caller options
    const defaultConfig: RequestClientOptions = {
      headers: {
        'Content-Type': 'application/json;charset=utf-8',
      },
      responseReturn: 'raw',
      // 默认超时时间 / Default request timeout (ms)
      timeout: 10_000,
    };
    const { ...axiosConfig } = options;
    const requestConfig = merge(axiosConfig, defaultConfig);
    requestConfig.paramsSerializer = getParamsSerializer(
      requestConfig.paramsSerializer,
    );
    this.instance = axios.create(requestConfig);

    bindMethods(this);

    // 实例化拦截器管理器 / Axios interceptors
    const interceptorManager = new InterceptorManager(this.instance);
    this.addRequestInterceptor =
      interceptorManager.addRequestInterceptor.bind(interceptorManager);
    this.addResponseInterceptor =
      interceptorManager.addResponseInterceptor.bind(interceptorManager);

    // 实例化文件上传器 / Multipart upload helper
    const fileUploader = new FileUploader(this);
    this.upload = fileUploader.upload.bind(fileUploader);
    // 实例化文件下载器 / Blob download helper
    const fileDownloader = new FileDownloader(this);
    this.download = fileDownloader.download.bind(fileDownloader);
    // 实例化 SSE 模块 / Server-Sent Events helpers
    const sse = new SSE(this);
    this.postSSE = sse.postSSE.bind(sse);
    this.requestSSE = sse.requestSSE.bind(sse);
  }

  /**
   * DELETE 请求 / HTTP DELETE
   */
  public delete<T = any>(
    url: string,
    config?: RequestClientConfig,
  ): Promise<T> {
    return this.request<T>(url, { ...config, method: 'DELETE' });
  }

  /**
   * GET 请求 / HTTP GET
   */
  public get<T = any>(url: string, config?: RequestClientConfig): Promise<T> {
    return this.request<T>(url, { ...config, method: 'GET' });
  }

  /**
   * 获取基础 URL / Axios baseURL
   */
  public getBaseUrl() {
    return this.instance.defaults.baseURL;
  }

  /**
   * POST 请求 / HTTP POST
   */
  public post<T = any>(
    url: string,
    data?: any,
    config?: RequestClientConfig,
  ): Promise<T> {
    return this.request<T>(url, { ...config, data, method: 'POST' });
  }

  /**
   * PUT 请求 / HTTP PUT
   */
  public put<T = any>(
    url: string,
    data?: any,
    config?: RequestClientConfig,
  ): Promise<T> {
    return this.request<T>(url, { ...config, data, method: 'PUT' });
  }

  /**
   * 通用请求 / Low-level request wrapper
   */
  public async request<T>(
    url: string,
    config: RequestClientConfig,
  ): Promise<T> {
    try {
      const response: AxiosResponse<T> = await this.instance({
        url,
        ...config,
        ...(config.paramsSerializer
          ? { paramsSerializer: getParamsSerializer(config.paramsSerializer) }
          : {}),
      });
      return response as T;
    } catch (error: any) {
      throw error.response ? error.response.data : error;
    }
  }
}

export { RequestClient };
