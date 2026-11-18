import{api}from'./api.js';
export const state={user:null,data:null};
export async function refresh(){
  state.data=await api('/archive');
  try{Object.assign(state.data,await api('/models'))}catch(e){/* 模型注册表尚未就绪时页面仍可渲染 */}
}
