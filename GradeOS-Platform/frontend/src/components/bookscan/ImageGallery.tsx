'use client';

import React, { useState } from 'react';
import { Trash2, Eye, ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { Button, Empty, Modal, Image } from 'antd';
import { ScannedImage } from './types';

interface ImageGalleryProps {
  images: ScannedImage[];
  onDelete: (ids: string[]) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}

export const ImageGallery: React.FC<ImageGalleryProps> = ({ images, onDelete, onReorder }) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const toggleSelect = (id: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedIds(newSet);
  };

  const selectAll = () => {
    if (selectedIds.size === images.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(images.map(img => img.id)));
  };

  const handleBulkDelete = () => {
    if (selectedIds.size === 0) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定删除选中的 ${selectedIds.size} 张图片？`,
      onOk: () => { onDelete(Array.from(selectedIds)); setSelectedIds(new Set()); }
    });
  };

  const handleMove = (index: number, direction: 'left' | 'right') => {
    const newIndex = direction === 'left' ? index - 1 : index + 1;
    if (newIndex >= 0 && newIndex < images.length) onReorder(index, newIndex);
  };

  if (images.length === 0) return <div className="h-full flex items-center justify-center"><Empty description="暂无扫描图片" /></div>;

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-3 bg-white border-b">
        <span className="text-sm text-gray-500">共 {images.length} 张</span>
        <div className="flex gap-2">
          <Button size="small" onClick={selectAll}>{selectedIds.size === images.length ? '取消全选' : '全选'}</Button>
          <Button size="small" danger icon={<Trash2 size={14} />} disabled={selectedIds.size === 0} onClick={handleBulkDelete}>删除 ({selectedIds.size})</Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {images.map((img, index) => (
            <div key={img.id} className={`relative group bg-white rounded-lg shadow-sm border overflow-hidden transition-all ${selectedIds.has(img.id) ? 'ring-2 ring-blue-500' : ''}`}>
              <div className="aspect-[3/4] relative bg-gray-100">
                <img src={img.url} alt={img.name} className="w-full h-full object-cover" loading="lazy" />
                <button className={`absolute top-2 left-2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${selectedIds.has(img.id) ? 'bg-blue-500 text-white' : 'bg-black/30 text-white hover:bg-black/50'}`} onClick={() => toggleSelect(img.id)}>
                  {selectedIds.has(img.id) && <Check size={12} />}
                </button>
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                  <Button type="primary" shape="circle" icon={<Eye size={14} />} onClick={() => setPreviewImage(img.url)} />
                  <Button shape="circle" icon={<ArrowLeft size={14} />} disabled={index === 0} onClick={() => handleMove(index, 'left')} />
                  <Button shape="circle" icon={<ArrowRight size={14} />} disabled={index === images.length - 1} onClick={() => handleMove(index, 'right')} />
                  <Button shape="circle" danger icon={<Trash2 size={14} />} onClick={() => onDelete([img.id])} />
                </div>
              </div>
              <div className="p-2 text-xs text-gray-500 flex items-center justify-between">
                <span className="truncate">{img.name}</span>
                <span className="bg-gray-100 px-2 py-0.5 rounded">{index + 1}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <Image style={{ display: 'none' }} preview={{ visible: !!previewImage, src: previewImage || '', onVisibleChange: (visible) => !visible && setPreviewImage(null) }} />
    </div>
  );
};
