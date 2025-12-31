import { useState, useCallback } from "react";
import axios from "axios";
import { Upload, Download, X, Filter, Image as ImageIcon, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const HomePage = () => {
  const [photos, setPhotos] = useState([]);
  const [filter, setFilter] = useState("all");
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files).filter(file => 
      file.type.startsWith('image/')
    );
    
    if (files.length === 0) {
      toast.error("Nenhuma imagem válida encontrada");
      return;
    }
    
    await uploadPhotos(files);
  }, []);

  const handleFileInput = useCallback(async (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      await uploadPhotos(files);
    }
  }, []);

  const uploadPhotos = async (files) => {
    setIsAnalyzing(true);
    toast.info(`Analisando ${files.length} foto(s)...`);
    
    try {
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      
      const response = await axios.post(`${API}/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setPhotos(prev => [...response.data.photos, ...prev]);
      toast.success(`${response.data.analyzed} foto(s) analisada(s) com sucesso!`);
    } catch (error) {
      console.error('Upload error:', error);
      toast.error("Erro ao analisar fotos");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const downloadGoodPhotos = () => {
    const goodPhotos = photos.filter(p => p.is_good);
    
    if (goodPhotos.length === 0) {
      toast.error("Nenhuma foto boa para baixar");
      return;
    }
    
    goodPhotos.forEach((photo, index) => {
      setTimeout(() => {
        const link = document.createElement('a');
        link.href = photo.image_data;
        link.download = `good_${photo.filename}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }, index * 100);
    });
    
    toast.success(`Download de ${goodPhotos.length} foto(s) iniciado!`);
  };

  const filteredPhotos = photos.filter(photo => {
    if (filter === "good") return photo.is_good;
    if (filter === "bad") return !photo.is_good;
    return true;
  });

  const stats = {
    total: photos.length,
    good: photos.filter(p => p.is_good).length,
    bad: photos.filter(p => !p.is_good).length
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-border/50">
        <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent" />
        <div className="container mx-auto px-6 md:px-12 py-12 relative">
          <div className="max-w-3xl">
            <h1 
              className="text-4xl md:text-6xl font-bold tracking-tight mb-4"
              style={{ fontFamily: 'Manrope, sans-serif' }}
              data-testid="main-heading"
            >
              Photo Selector
            </h1>
            <p className="text-lg text-muted-foreground mb-8" data-testid="subtitle">
              Análise inteligente de fotos com IA.
            </p>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 md:px-12 py-8">
        {/* Stats */}
        {stats.total > 0 && (
          <div className="grid grid-cols-3 gap-4 mb-8" data-testid="stats-section">
            <Card className="p-6 bg-card border-border">
              <div className="text-2xl font-bold" data-testid="total-count">{stats.total}</div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Total</div>
            </Card>
            <Card className="p-6 bg-card border-border">
              <div className="text-2xl font-bold text-green-500" data-testid="good-count">{stats.good}</div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Aprovadas</div>
            </Card>
            <Card className="p-6 bg-card border-border">
              <div className="text-2xl font-bold text-red-400" data-testid="bad-count">{stats.bad}</div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Rejeitadas</div>
            </Card>
          </div>
        )}

        {/* Upload Area */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative mb-8 border-2 border-dashed rounded-lg transition-all duration-300 ${
            isDragging ? 'border-accent bg-accent/5 scale-[1.02]' : 'border-border bg-card/50'
          }`}
          data-testid="upload-area"
        >
          <div className="p-12 text-center">
            <Upload className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-xl font-semibold mb-2" style={{ fontFamily: 'Manrope, sans-serif' }}>
              {isDragging ? 'Solte as fotos aqui' : 'Arraste fotos ou clique para selecionar'}
            </h3>
            <p className="text-sm text-muted-foreground mb-6">
              Formatos aceitos: JPG, PNG, WEBP
            </p>
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={handleFileInput}
              className="hidden"
              id="file-input"
              data-testid="file-input"
            />
            <Button 
              className="rounded-full px-8 py-6 cursor-pointer"
              disabled={isAnalyzing}
              data-testid="select-files-button"
              onClick={() => document.getElementById('file-input').click()}
            >
              {isAnalyzing ? 'Analisando...' : 'Selecionar Fotos'}
            </Button>
          </div>
        </div>

        {/* Filter & Download */}
        {photos.length > 0 && (
          <div className="flex justify-between items-center mb-6" data-testid="controls-section">
            <ToggleGroup type="single" value={filter} onValueChange={(v) => v && setFilter(v)} data-testid="filter-toggle">
              <ToggleGroupItem value="all" className="rounded-full" data-testid="filter-all">
                Todas ({stats.total})
              </ToggleGroupItem>
              <ToggleGroupItem value="good" className="rounded-full" data-testid="filter-good">
                Boas ({stats.good})
              </ToggleGroupItem>
              <ToggleGroupItem value="bad" className="rounded-full" data-testid="filter-bad">
                Ruins ({stats.bad})
              </ToggleGroupItem>
            </ToggleGroup>

            <Button
              onClick={downloadGoodPhotos}
              disabled={stats.good === 0}
              className="rounded-full"
              data-testid="download-button"
            >
              <Download className="w-4 h-4 mr-2" />
              Baixar Boas ({stats.good})
            </Button>
          </div>
        )}

        {/* Gallery */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4" data-testid="photo-gallery">
          {filteredPhotos.map((photo) => (
            <Card
              key={photo.id}
              className="group relative overflow-hidden rounded-lg border border-border bg-card hover:border-accent/50 transition-colors"
              data-testid={`photo-card-${photo.id}`}
            >
              <div className="aspect-square relative">
                <img
                  src={photo.image_data}
                  alt={photo.filename}
                  className="w-full h-full object-cover"
                  data-testid={`photo-image-${photo.id}`}
                />
                
                {/* Status Badge */}
                <div className="absolute top-2 right-2">
                  {photo.is_good ? (
                    <Badge className="bg-green-500/90 hover:bg-green-500" data-testid={`badge-good-${photo.id}`}>
                      <Check className="w-3 h-3 mr-1" /> Boa
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="bg-red-500/90" data-testid={`badge-bad-${photo.id}`}>
                      <X className="w-3 h-3 mr-1" /> Ruim
                    </Badge>
                  )}
                </div>

                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/80 opacity-0 group-hover:opacity-100 transition-opacity p-4 flex flex-col justify-end" data-testid={`photo-overlay-${photo.id}`}>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span>Nitidez</span>
                      <span className="font-mono">{photo.sharpness_score.toFixed(1)}/10</span>
                    </div>
                    <Progress value={photo.sharpness_score * 10} className="h-1" />
                    
                    <div className="flex justify-between">
                      <span>Ruído</span>
                      <span className="font-mono">{photo.noise_score.toFixed(1)}/10</span>
                    </div>
                    <Progress value={photo.noise_score * 10} className="h-1" />
                    
                    <div className="flex justify-between">
                      <span>Composição</span>
                      <span className="font-mono">{photo.composition_score.toFixed(1)}/10</span>
                    </div>
                    <Progress value={photo.composition_score * 10} className="h-1" />
                    
                    <div className="flex justify-between">
                      <span>Exposição</span>
                      <span className="font-mono">{photo.exposure_score.toFixed(1)}/10</span>
                    </div>
                    <Progress value={photo.exposure_score * 10} className="h-1" />
                    
                    <div className="pt-2 border-t border-white/20 flex justify-between font-semibold">
                      <span>Geral</span>
                      <span className="font-mono">{photo.overall_score.toFixed(1)}/10</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="p-3">
                <p className="text-xs truncate text-muted-foreground" data-testid={`photo-filename-${photo.id}`}>
                  {photo.filename}
                </p>
              </div>
            </Card>
          ))}
        </div>

        {filteredPhotos.length === 0 && photos.length > 0 && (
          <div className="text-center py-16" data-testid="no-filtered-photos">
            <ImageIcon className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
            <p className="text-muted-foreground">Nenhuma foto neste filtro</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default HomePage;